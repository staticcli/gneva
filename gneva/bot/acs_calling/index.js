/**
 * ACS Calling SDK — joins a Teams meeting and streams audio bidirectionally.
 *
 * Loaded in Playwright. Receives config via window.__gnevaConfig:
 *   { token, meetingLink, wsUrl, displayName }
 *
 * Audio flow:
 *   Incoming: ACS remote audio → AudioContext → PCM16 → WebSocket → Python STT
 *   Outgoing: Python TTS → WebSocket → AudioContext → LocalAudioStream → ACS call
 */

const { CallClient, LocalAudioStream, Features } = require("@azure/communication-calling");
const { AzureCommunicationTokenCredential } = require("@azure/communication-common");

// Expose the join function globally so Playwright can call it
window.__gnevaACS = {
    call: null,
    callAgent: null,
    ws: null,
    audioContext: null,
    outgoingContext: null,
    outgoingDest: null,
    localAudioStream: null,
    status: "initializing",
    error: null,
    participants: {},
    trackCount: 0,

    async join(config) {
        const { token, meetingLink, wsUrl, displayName } = config;
        this.status = "connecting";
        console.log("[ACS] Joining meeting:", meetingLink, "as", displayName);

        try {
            // 1. Create CallClient and CallAgent
            const callClient = new CallClient();
            const credential = new AzureCommunicationTokenCredential(token);
            this.callAgent = await callClient.createCallAgent(credential, {
                displayName: displayName || "Gneva",
            });
            console.log("[ACS] CallAgent created");

            // 2. Set up outgoing audio (silence initially, TTS will replace)
            this.outgoingContext = new AudioContext({ sampleRate: 16000 });
            this.outgoingDest = this.outgoingContext.createMediaStreamDestination();
            // Create a silent oscillator to keep the stream alive
            const silentOsc = this.outgoingContext.createOscillator();
            const silentGain = this.outgoingContext.createGain();
            silentGain.gain.value = 0; // silent
            silentOsc.connect(silentGain);
            silentGain.connect(this.outgoingDest);
            silentOsc.start();
            this.localAudioStream = new LocalAudioStream(this.outgoingDest.stream);
            console.log("[ACS] Outgoing audio stream ready (silent)");

            // 3. Join the Teams meeting
            this.call = this.callAgent.join(
                { meetingLink: meetingLink },
                {
                    audioOptions: {
                        localAudioStreams: [this.localAudioStream],
                        muted: false,
                    },
                }
            );
            console.log("[ACS] Join initiated, waiting for connection...");

            // 4. Connect WebSocket for audio streaming to Python
            this._connectWebSocket(wsUrl);

            // 5. Set up call event handlers
            this.call.on("stateChanged", () => {
                const state = this.call.state;
                console.log("[ACS] Call state:", state);
                this.status = state;

                if (state === "Connected") {
                    console.log("[ACS] Connected to meeting!");
                    this._startAudioCapture();
                } else if (state === "Disconnected") {
                    console.log("[ACS] Disconnected from meeting");
                    this._cleanup();
                }
            });

            // Track remote participants
            this.call.on("remoteParticipantsUpdated", (e) => {
                e.added.forEach((p) => {
                    const name = p.displayName || "Participant";
                    const id = p.identifier?.communicationUserId ||
                               p.identifier?.microsoftTeamsUserId ||
                               p.identifier?.rawId || "unknown";
                    console.log("[ACS] Participant joined:", name, id);
                    this.participants[id] = name;
                    this._attachParticipantAudio(p);
                });
                e.removed.forEach((p) => {
                    const id = p.identifier?.communicationUserId ||
                               p.identifier?.microsoftTeamsUserId ||
                               p.identifier?.rawId || "unknown";
                    console.log("[ACS] Participant left:", this.participants[id] || id);
                    delete this.participants[id];
                });
            });

            // Handle existing participants
            this.call.remoteParticipants.forEach((p) => {
                const name = p.displayName || "Participant";
                const id = p.identifier?.communicationUserId ||
                           p.identifier?.microsoftTeamsUserId ||
                           p.identifier?.rawId || "unknown";
                this.participants[id] = name;
                this._attachParticipantAudio(p);
            });

        } catch (err) {
            console.error("[ACS] Join error:", err);
            this.status = "failed";
            this.error = err.message;
            throw err;
        }
    },

    _connectWebSocket(wsUrl) {
        console.log("[ACS] Connecting WebSocket:", wsUrl);
        this.ws = new WebSocket(wsUrl);
        this.ws.binaryType = "arraybuffer";

        this.ws.onopen = () => {
            console.log("[ACS] WebSocket connected");
        };

        this.ws.onmessage = (event) => {
            // Incoming TTS audio from Python — play into the call
            if (event.data instanceof ArrayBuffer) {
                this._playTTSAudio(new Uint8Array(event.data));
            }
        };

        this.ws.onclose = () => {
            console.log("[ACS] WebSocket closed");
        };

        this.ws.onerror = (err) => {
            console.error("[ACS] WebSocket error:", err);
        };
    },

    _attachParticipantAudio(participant) {
        // Listen for audio streams from this participant
        const id = participant.identifier?.communicationUserId ||
                   participant.identifier?.microsoftTeamsUserId ||
                   participant.identifier?.rawId || "unknown";

        participant.on("audioStreamsUpdated", (e) => {
            e.added.forEach((audioStream) => {
                if (audioStream.isAvailable) {
                    this._captureParticipantStream(audioStream, id);
                }
                audioStream.on("isAvailableChanged", () => {
                    if (audioStream.isAvailable) {
                        this._captureParticipantStream(audioStream, id);
                    }
                });
            });
        });

        // Check existing audio streams
        if (participant.audioStreams) {
            participant.audioStreams.forEach((audioStream) => {
                if (audioStream.isAvailable) {
                    this._captureParticipantStream(audioStream, id);
                }
                audioStream.on("isAvailableChanged", () => {
                    if (audioStream.isAvailable) {
                        this._captureParticipantStream(audioStream, id);
                    }
                });
            });
        }
    },

    async _captureParticipantStream(audioStream, participantId) {
        try {
            const mediaStream = await audioStream.getMediaStream();
            if (!mediaStream) {
                console.warn("[ACS] No MediaStream from participant", participantId);
                return;
            }

            const tracks = mediaStream.getAudioTracks();
            console.log("[ACS] MediaStream from", participantId,
                        "has", tracks.length, "audio tracks,",
                        "active:", mediaStream.active);
            tracks.forEach((t, i) => {
                console.log("[ACS]   track", i, "enabled:", t.enabled,
                            "readyState:", t.readyState, "label:", t.label);
            });

            if (tracks.length === 0 || !mediaStream.active) {
                console.warn("[ACS] No active audio tracks for participant", participantId);
                return;
            }

            const trackId = ++this.trackCount;
            console.log("[ACS] Capturing audio from participant", participantId,
                        "-> track", trackId, "name:", this.participants[participantId]);

            // Create per-participant AudioContext for PCM extraction
            const ctx = new AudioContext({ sampleRate: 16000 });
            // CRITICAL: Resume AudioContext (suspended by default in headless Chrome)
            if (ctx.state === "suspended") {
                await ctx.resume();
                console.log("[ACS] AudioContext resumed for track", trackId, "state:", ctx.state);
            }

            const source = ctx.createMediaStreamSource(mediaStream);
            const processor = ctx.createScriptProcessor(4096, 1, 1);

            let chunksSent = 0;
            processor.onaudioprocess = (e) => {
                if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

                const inputData = e.inputBuffer.getChannelData(0);

                // Log first few chunks for debugging
                if (chunksSent < 3) {
                    let maxVal = 0;
                    for (let i = 0; i < inputData.length; i++) {
                        const abs = Math.abs(inputData[i]);
                        if (abs > maxVal) maxVal = abs;
                    }
                    console.log("[ACS] Track", trackId, "chunk", chunksSent,
                                "samples:", inputData.length, "maxAmplitude:", maxVal.toFixed(6));
                }

                // Convert float32 to int16 PCM
                const pcm16 = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }

                // Send with 4-byte track ID header (matches audio_capture.py format)
                const header = new ArrayBuffer(4);
                new DataView(header).setUint32(0, trackId, false); // big-endian
                const msg = new Uint8Array(4 + pcm16.byteLength);
                msg.set(new Uint8Array(header), 0);
                msg.set(new Uint8Array(pcm16.buffer), 4);
                this.ws.send(msg.buffer);
                chunksSent++;
            };

            source.connect(processor);
            processor.connect(ctx.destination);
            console.log("[ACS] Audio pipeline created for track", trackId,
                        "AudioContext state:", ctx.state);

        } catch (err) {
            console.error("[ACS] Failed to capture participant audio:", err.message, err.stack);
        }
    },

    _startAudioCapture() {
        // Log what's available on the call object for debugging
        console.log("[ACS] _startAudioCapture called");
        console.log("[ACS] call.remoteParticipants:", this.call.remoteParticipants?.length || 0);
        console.log("[ACS] call.state:", this.call.state);
        console.log("[ACS] call.isLocalAudioStarted:", this.call.isLocalAudioStarted);
        console.log("[ACS] WS state:", this.ws ? this.ws.readyState : "no ws");

        // Capture mixed remote audio as a fallback (track 0)
        try {
            const remoteStreams = this.call.remoteAudioStreams;
            console.log("[ACS] remoteAudioStreams:", remoteStreams?.length || 0);
            if (remoteStreams && remoteStreams.length > 0) {
                remoteStreams.forEach(async (stream) => {
                    console.log("[ACS] Remote stream available:", stream.isAvailable,
                                "mediaStreamType:", stream.mediaStreamType);
                    if (stream.isAvailable) {
                        try {
                            const ms = await stream.getMediaStream();
                            if (ms) {
                                await this._captureRemoteMixed(ms);
                            } else {
                                console.warn("[ACS] getMediaStream returned null");
                            }
                        } catch (e) {
                            console.error("[ACS] getMediaStream error:", e.message);
                        }
                    }
                    stream.on("isAvailableChanged", async () => {
                        console.log("[ACS] Remote stream isAvailable changed:", stream.isAvailable);
                        if (stream.isAvailable) {
                            try {
                                const ms = await stream.getMediaStream();
                                if (ms) {
                                    await this._captureRemoteMixed(ms);
                                }
                            } catch (e) {
                                console.error("[ACS] getMediaStream error:", e.message);
                            }
                        }
                    });
                });
            } else {
                console.log("[ACS] No remoteAudioStreams — will rely on per-participant capture");
            }
        } catch (err) {
            console.log("[ACS] Remote audio stream setup error:", err.message);
        }

        // Also re-check existing participants (they may have joined before Connected)
        try {
            this.call.remoteParticipants.forEach((p) => {
                const name = p.displayName || "Participant";
                const id = p.identifier?.communicationUserId ||
                           p.identifier?.microsoftTeamsUserId ||
                           p.identifier?.rawId || "unknown";
                console.log("[ACS] Re-checking participant audio:", name, id);
                console.log("[ACS]   audioStreams:", p.audioStreams?.length || 0);
                this._attachParticipantAudio(p);
            });
        } catch (err) {
            console.log("[ACS] Participant re-check error:", err.message);
        }
    },

    async _captureRemoteMixed(mediaStream) {
        // Track 0 = mixed audio fallback
        const tracks = mediaStream.getAudioTracks();
        console.log("[ACS] Capturing mixed remote audio (track 0),",
                    tracks.length, "audio tracks, active:", mediaStream.active);

        const ctx = new AudioContext({ sampleRate: 16000 });
        // CRITICAL: Resume AudioContext
        if (ctx.state === "suspended") {
            await ctx.resume();
            console.log("[ACS] Mixed AudioContext resumed, state:", ctx.state);
        }

        const source = ctx.createMediaStreamSource(mediaStream);
        const processor = ctx.createScriptProcessor(4096, 1, 1);

        let chunksSent = 0;
        processor.onaudioprocess = (e) => {
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

            const inputData = e.inputBuffer.getChannelData(0);

            if (chunksSent < 3) {
                let maxVal = 0;
                for (let i = 0; i < inputData.length; i++) {
                    const abs = Math.abs(inputData[i]);
                    if (abs > maxVal) maxVal = abs;
                }
                console.log("[ACS] Mixed track chunk", chunksSent,
                            "samples:", inputData.length, "maxAmplitude:", maxVal.toFixed(6));
            }

            const pcm16 = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
                const s = Math.max(-1, Math.min(1, inputData[i]));
                pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }

            const header = new ArrayBuffer(4);
            new DataView(header).setUint32(0, 0, false); // track 0 = mixed
            const msg = new Uint8Array(4 + pcm16.byteLength);
            msg.set(new Uint8Array(header), 0);
            msg.set(new Uint8Array(pcm16.buffer), 4);
            this.ws.send(msg.buffer);
            chunksSent++;
        };

        source.connect(processor);
        processor.connect(ctx.destination);
    },

    _playTTSAudio(pcmData) {
        // Receive PCM16 16kHz from Python TTS and play into the outgoing audio stream
        if (!this.outgoingContext || !this.outgoingDest) return;

        try {
            // Convert PCM16 bytes to float32
            const int16 = new Int16Array(pcmData.buffer, pcmData.byteOffset, pcmData.byteLength / 2);
            const float32 = new Float32Array(int16.length);
            for (let i = 0; i < int16.length; i++) {
                float32[i] = int16[i] / 32768.0;
            }

            // Create audio buffer and play
            const buffer = this.outgoingContext.createBuffer(1, float32.length, 16000);
            buffer.getChannelData(0).set(float32);

            const bufferSource = this.outgoingContext.createBufferSource();
            bufferSource.buffer = buffer;
            bufferSource.connect(this.outgoingDest);
            bufferSource.start();
        } catch (err) {
            console.error("[ACS] TTS playback error:", err);
        }
    },

    async leave() {
        console.log("[ACS] Leaving meeting...");
        try {
            if (this.call) {
                await this.call.hangUp();
            }
        } catch (err) {
            console.error("[ACS] Leave error:", err);
        }
        this._cleanup();
    },

    _cleanup() {
        if (this.ws) {
            try { this.ws.close(); } catch (e) {}
            this.ws = null;
        }
        if (this.outgoingContext) {
            try { this.outgoingContext.close(); } catch (e) {}
        }
        this.status = "ended";
    },
};

console.log("[ACS] Module loaded — window.__gnevaACS ready");
