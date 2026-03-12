/**
 * Gneva Audio Capture — injected into meeting pages via CDP.
 * Captures per-speaker audio from WebRTC tracks, sends PCM over WebSocket
 * with track ID prefix for speaker separation.
 *
 * Each remote audio track gets its own AudioContext + ScriptProcessorNode.
 * Audio chunks are sent as: [4-byte track ID (uint32 BE)] + [PCM16 data]
 */
(function() {
  const WS_URL = '__WS_URL__';  // replaced by Python before injection
  const SAMPLE_RATE = 16000;
  const BUFFER_SIZE = 4096;

  let ws = null;
  let reconnectTimer = null;

  // Per-track processing chains: trackKey -> { ctx, source, processor, trackId }
  const trackChains = new Map();
  let nextTrackId = 1;

  // Track IDs assigned by track key (stream.id or track.id)
  const trackIdMap = new Map();

  // Connected media elements (for DOM-based capture fallback)
  const connectedElements = new Set();

  // Shared AudioContext for DOM element capture (fallback path)
  let fallbackCtx = null;
  let fallbackProcessor = null;
  const FALLBACK_TRACK_ID = 0;  // track ID 0 = mixed/unknown source

  function connectWS() {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    try {
      ws = new WebSocket(WS_URL);
      ws.binaryType = 'arraybuffer';
      ws.onopen = () => console.log('[Gneva] Audio capture WebSocket connected');
      ws.onclose = () => {
        console.log('[Gneva] WebSocket closed, reconnecting in 2s...');
        if (!reconnectTimer) reconnectTimer = setTimeout(() => { reconnectTimer = null; connectWS(); }, 2000);
      };
      ws.onerror = (e) => console.error('[Gneva] WebSocket error:', e);
    } catch (e) {
      console.error('[Gneva] WebSocket connect failed:', e);
    }
  }

  function getTrackId(key) {
    if (trackIdMap.has(key)) return trackIdMap.get(key);
    const id = nextTrackId++;
    trackIdMap.set(key, id);
    return id;
  }

  /**
   * Send PCM audio with a 4-byte track ID header.
   * Format: [uint32 BE trackId][int16 PCM samples...]
   */
  function sendWithTrackId(trackId, float32Input) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    // 4 bytes header + 2 bytes per sample
    const buf = new ArrayBuffer(4 + float32Input.length * 2);
    const view = new DataView(buf);
    // Write track ID as big-endian uint32
    view.setUint32(0, trackId, false);
    // Convert float32 to int16
    const pcm16 = new Int16Array(buf, 4);
    for (let i = 0; i < float32Input.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Input[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    ws.send(buf);
  }

  /**
   * Create a per-track audio processing chain.
   * Each track gets its own AudioContext → MediaStreamSource → ScriptProcessor → WS.
   */
  function createTrackChain(stream, trackKey) {
    if (trackChains.has(trackKey)) {
      console.log('[Gneva] Track chain already exists for:', trackKey);
      return;
    }

    const trackId = getTrackId(trackKey);

    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(BUFFER_SIZE, 1, 1);

      processor.onaudioprocess = function(e) {
        const input = e.inputBuffer.getChannelData(0);
        sendWithTrackId(trackId, input);
      };

      source.connect(processor);
      // Connect to destination to keep the processor alive (required by spec)
      processor.connect(ctx.destination);

      const chain = { ctx, source, processor, trackId, trackKey };
      trackChains.set(trackKey, chain);

      // Listen for track ended to clean up
      const audioTracks = stream.getAudioTracks();
      if (audioTracks.length > 0) {
        audioTracks.forEach(track => {
          track.addEventListener('ended', () => {
            console.log('[Gneva] Audio track ended:', trackKey, '(trackId:', trackId, ')');
            cleanupTrackChain(trackKey);
          });
        });
      }

      console.log('[Gneva] Created per-track chain: trackKey=' + trackKey + ', trackId=' + trackId +
                   ', audioTracks=' + audioTracks.length);
    } catch (e) {
      console.warn('[Gneva] Failed to create track chain for', trackKey, ':', e.message);
    }
  }

  function cleanupTrackChain(trackKey) {
    const chain = trackChains.get(trackKey);
    if (!chain) return;
    try {
      chain.processor.disconnect();
      chain.source.disconnect();
      chain.ctx.close();
    } catch (e) {
      console.warn('[Gneva] Cleanup error for', trackKey, ':', e.message);
    }
    trackChains.delete(trackKey);
    console.log('[Gneva] Cleaned up track chain:', trackKey, '(active chains:', trackChains.size, ')');
  }

  /**
   * Initialize fallback AudioContext for DOM media element capture.
   * Used when audio comes through <audio>/<video> elements instead of direct WebRTC tracks.
   * This is the mixed-audio path (track ID 0) — less ideal but works as fallback.
   */
  function initFallbackAudio() {
    if (fallbackCtx) return;
    fallbackCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });

    fallbackProcessor = fallbackCtx.createScriptProcessor(BUFFER_SIZE, 1, 1);
    fallbackProcessor.onaudioprocess = function(e) {
      const input = e.inputBuffer.getChannelData(0);
      sendWithTrackId(FALLBACK_TRACK_ID, input);
    };

    // We'll connect sources to a merger, then merger to processor
    window.__gnevaFallbackMerger = fallbackCtx.createChannelMerger(1);
    window.__gnevaFallbackMerger.connect(fallbackProcessor);
    fallbackProcessor.connect(fallbackCtx.destination);

    console.log('[Gneva] Fallback audio context initialized (track ID 0 = mixed)');
  }

  function captureElement(el) {
    if (connectedElements.has(el)) return;
    if (!el.srcObject && !el.src) return;

    try {
      initFallbackAudio();
      let source;

      if (el.srcObject) {
        source = fallbackCtx.createMediaStreamSource(el.srcObject);
      } else if (el.src && el.src.startsWith('blob:')) {
        source = fallbackCtx.createMediaElementSource(el);
      } else {
        return;
      }

      source.connect(window.__gnevaFallbackMerger);
      connectedElements.add(el);
      console.log('[Gneva] Capturing audio element (fallback path):', el.tagName, el.id || '(no id)');
    } catch (e) {
      if (!e.message.includes('already connected')) {
        console.warn('[Gneva] Could not capture element:', e.message);
      }
    }
  }

  function scanForMedia() {
    document.querySelectorAll('audio, video').forEach(el => {
      captureElement(el);

      if (!connectedElements.has(el)) {
        const origSet = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'srcObject')?.set;
        if (origSet && !el.__gneva_hooked) {
          el.__gneva_hooked = true;
          Object.defineProperty(el, 'srcObject', {
            set(v) {
              origSet.call(this, v);
              setTimeout(() => captureElement(this), 100);
            },
            get() {
              return Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'srcObject').get.call(this);
            }
          });
        }
      }
    });
  }

  // Observe DOM for dynamically added media elements
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      for (const node of m.addedNodes) {
        if (node.nodeType !== 1) continue;
        if (node.tagName === 'AUDIO' || node.tagName === 'VIDEO') {
          setTimeout(() => captureElement(node), 200);
        }
        if (node.querySelectorAll) {
          node.querySelectorAll('audio, video').forEach(el => {
            setTimeout(() => captureElement(el), 200);
          });
        }
      }
    }
  });
  observer.observe(document.body || document.documentElement, { childList: true, subtree: true });

  // Hook RTCPeerConnection to catch WebRTC audio tracks — per-track separation
  const OrigRTC = window.RTCPeerConnection;
  if (OrigRTC) {
    window.RTCPeerConnection = function(...args) {
      const pc = new OrigRTC(...args);

      pc.addEventListener('track', (event) => {
        if (event.track.kind === 'audio') {
          const stream = event.streams.length > 0 ? event.streams[0] : new MediaStream([event.track]);
          // Use stream.id as the track key (stable across renegotiations)
          const trackKey = stream.id || event.track.id || ('track_' + nextTrackId);

          console.log('[Gneva] WebRTC audio track received: trackKey=' + trackKey +
                       ', track.id=' + event.track.id +
                       ', track.label=' + (event.track.label || 'none') +
                       ', streams=' + event.streams.length +
                       ', track.readyState=' + event.track.readyState +
                       ', track.muted=' + event.track.muted);

          // Create separate processing chain for this track
          createTrackChain(stream, trackKey);

          // Log track state changes for diagnostics
          event.track.addEventListener('mute', () => {
            console.log('[Gneva] Track muted:', trackKey);
          });
          event.track.addEventListener('unmute', () => {
            console.log('[Gneva] Track unmuted:', trackKey);
          });
        } else {
          console.log('[Gneva] Non-audio track received: kind=' + event.track.kind);
        }
      });

      return pc;
    };
    window.RTCPeerConnection.prototype = OrigRTC.prototype;
    Object.getOwnPropertyNames(OrigRTC).forEach(prop => {
      if (prop !== 'prototype' && prop !== 'length' && prop !== 'name') {
        try { window.RTCPeerConnection[prop] = OrigRTC[prop]; } catch(e) {}
      }
    });
  }

  // Handle pre-captured tracks (from the early init_script hook)
  function connectPreCapturedTracks() {
    if (window.__gnevaIncomingAudioTracks && window.__gnevaIncomingAudioTracks.length > 0) {
      console.log('[Gneva] Connecting', window.__gnevaIncomingAudioTracks.length, 'pre-captured audio tracks');
      window.__gnevaIncomingAudioTracks.forEach((stream, idx) => {
        const trackKey = stream.id || ('precaptured_' + idx);
        try {
          createTrackChain(stream, trackKey);
          console.log('[Gneva] Connected pre-captured track:', trackKey);
        } catch (e) {
          console.warn('[Gneva] Pre-captured track connect failed:', e.message);
        }
      });
    }
  }

  // Expose diagnostics globally for debugging from Python
  window.__gnevaAudioDiag = function() {
    const chains = [];
    trackChains.forEach((chain, key) => {
      chains.push({
        trackKey: key,
        trackId: chain.trackId,
        ctxState: chain.ctx.state,
      });
    });
    return {
      wsState: ws ? ws.readyState : -1,
      activeChains: trackChains.size,
      totalTracksEver: nextTrackId - 1,
      chains: chains,
      fallbackActive: !!fallbackCtx,
      connectedElements: connectedElements.size,
    };
  };

  // Start
  connectWS();
  connectPreCapturedTracks();
  scanForMedia();
  setInterval(scanForMedia, 3000);

  // Periodic diagnostic logging
  setInterval(() => {
    const diag = window.__gnevaAudioDiag();
    if (diag.activeChains > 0 || diag.connectedElements > 0) {
      console.log('[Gneva] Audio diag: ' + diag.activeChains + ' track chains, ' +
                   diag.connectedElements + ' DOM elements, WS=' +
                   (ws ? ['CONNECTING','OPEN','CLOSING','CLOSED'][ws.readyState] : 'null'));
    }
  }, 10000);

  console.log('[Gneva] Audio capture initialized (per-track mode), WS:', WS_URL);
})();
