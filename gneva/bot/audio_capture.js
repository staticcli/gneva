/**
 * Gneva Audio Capture — injected into meeting pages via CDP.
 * Captures all audio from <audio> and <video> elements, sends PCM over WebSocket.
 */
(function() {
  const WS_URL = '__WS_URL__';  // replaced by Python before injection
  const SAMPLE_RATE = 16000;
  const BUFFER_SIZE = 4096;

  let ws = null;
  let audioCtx = null;
  let merger = null;
  let processor = null;
  let connectedElements = new Set();
  let reconnectTimer = null;

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

  function initAudio() {
    if (audioCtx) return;
    audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });

    // Merger node — all sources connect here
    merger = audioCtx.createChannelMerger(1);

    // Processor node — converts float32 to int16 and sends over WS
    processor = audioCtx.createScriptProcessor(BUFFER_SIZE, 1, 1);
    processor.onaudioprocess = function(e) {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      const input = e.inputBuffer.getChannelData(0);
      const pcm16 = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      ws.send(pcm16.buffer);
    };

    merger.connect(processor);
    processor.connect(audioCtx.destination);
  }

  function captureElement(el) {
    if (connectedElements.has(el)) return;
    if (!el.srcObject && !el.src) return;

    try {
      initAudio();
      let source;

      if (el.srcObject) {
        // WebRTC MediaStream — most meeting audio comes through here
        source = audioCtx.createMediaStreamSource(el.srcObject);
      } else if (el.src && el.src.startsWith('blob:')) {
        // Blob URL — some platforms use this
        source = audioCtx.createMediaElementSource(el);
      } else {
        return;
      }

      source.connect(merger);
      connectedElements.add(el);
      console.log('[Gneva] Capturing audio from', el.tagName, el.id || '(no id)');
    } catch (e) {
      // createMediaElementSource can only be called once per element
      if (!e.message.includes('already connected')) {
        console.warn('[Gneva] Could not capture element:', e.message);
      }
    }
  }

  function scanForMedia() {
    document.querySelectorAll('audio, video').forEach(el => {
      captureElement(el);

      // Some elements get srcObject set after creation
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
        // Also check children
        if (node.querySelectorAll) {
          node.querySelectorAll('audio, video').forEach(el => {
            setTimeout(() => captureElement(el), 200);
          });
        }
      }
    }
  });
  observer.observe(document.body || document.documentElement, { childList: true, subtree: true });

  // Hook RTCPeerConnection to catch WebRTC audio tracks
  const OrigRTC = window.RTCPeerConnection;
  if (OrigRTC) {
    window.RTCPeerConnection = function(...args) {
      const pc = new OrigRTC(...args);
      const origOnTrack = pc.ontrack;

      pc.addEventListener('track', (event) => {
        if (event.track.kind === 'audio' && event.streams.length > 0) {
          try {
            initAudio();
            const source = audioCtx.createMediaStreamSource(event.streams[0]);
            source.connect(merger);
            console.log('[Gneva] Captured WebRTC audio track directly');
          } catch (e) {
            console.warn('[Gneva] WebRTC track capture failed:', e.message);
          }
        }
      });

      return pc;
    };
    window.RTCPeerConnection.prototype = OrigRTC.prototype;
    // Copy static properties
    Object.getOwnPropertyNames(OrigRTC).forEach(prop => {
      if (prop !== 'prototype' && prop !== 'length' && prop !== 'name') {
        try { window.RTCPeerConnection[prop] = OrigRTC[prop]; } catch(e) {}
      }
    });
  }

  // Start
  connectWS();
  scanForMedia();
  // Periodic rescan for elements added without DOM mutation
  setInterval(scanForMedia, 3000);

  console.log('[Gneva] Audio capture initialized, WS:', WS_URL);
})();
