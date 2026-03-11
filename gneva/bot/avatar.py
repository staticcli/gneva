"""Avatar system — generates a realistic virtual camera feed for Gneva in meetings.

Uses an HTML canvas rendered in the browser to create a professional-looking
AI team member avatar with idle animations and lip-sync when speaking.
The canvas stream replaces the fake camera device via getUserMedia override.
"""

import logging

logger = logging.getLogger(__name__)


def get_avatar_inject_js(face_image_b64: str | None = None) -> str:
    """Return JS that overrides getUserMedia to serve our canvas-based avatar.

    This must be injected BEFORE the meeting page requests camera access.
    It creates a hidden canvas, renders the avatar, and returns that stream
    whenever the page asks for a video track.

    Args:
        face_image_b64: Optional base64 data URL of a face photo. When provided,
            the avatar renders the photo instead of a cartoon face, with
            lip-sync and idle animations overlaid on top.
    """
    # Escape the base64 string for safe JS embedding (S1 fix: use json.dumps for XSS safety)
    import json
    face_b64_js = json.dumps(face_image_b64) if face_image_b64 else "null"

    # We use string replacement instead of f-string to avoid escaping hundreds of JS braces
    js = """
(function() {
    // ===== AVATAR RENDERING ENGINE =====
    const AVATAR_CONFIG = {
        width: 640,
        height: 480,
        fps: 30,
    };

    const FACE_IMAGE_B64 = __FACE_B64_PLACEHOLDER__;

    // Create offscreen canvas for avatar
    const avatarCanvas = document.createElement('canvas');
    avatarCanvas.width = AVATAR_CONFIG.width;
    avatarCanvas.height = AVATAR_CONFIG.height;
    const ctx = avatarCanvas.getContext('2d');

    // Load photo face image if provided
    let facePhoto = null;
    let facePhotoLoaded = false;
    if (FACE_IMAGE_B64) {
        facePhoto = new Image();
        facePhoto.onload = function() {
            facePhotoLoaded = true;
            console.log('[Gneva Avatar] Face photo loaded successfully');
        };
        facePhoto.onerror = function() {
            console.warn('[Gneva Avatar] Face photo failed to load, falling back to cartoon');
            facePhoto = null;
        };
        facePhoto.src = FACE_IMAGE_B64;
    }

    // Avatar state
    const state = {
        speaking: false,
        mouthOpen: 0,       // 0-1 mouth openness
        blinkTimer: 0,
        blinkState: 0,      // 0=open, 1=closing, 2=closed, 3=opening
        eyeTargetX: 0,
        eyeTargetY: 0,
        eyeX: 0,
        eyeY: 0,
        headTilt: 0,
        headTiltTarget: 0,
        breathCycle: 0,
        lastTime: 0,
        microExpressionTimer: 0,
        browRaise: 0,
        smileAmount: 0.15,  // slight resting smile
    };

    // === COLOR PALETTE ===
    const SKIN = '#E8C4A0';
    const SKIN_SHADOW = '#D4A574';
    const SKIN_HIGHLIGHT = '#F0D4B8';
    const HAIR_COLOR = '#2C1810';
    const HAIR_HIGHLIGHT = '#4A2C1C';
    const EYE_COLOR = '#3B7D5F';
    const EYE_DARK = '#1A3D2E';
    const LIP_COLOR = '#C47A6A';
    const LIP_DARK = '#A85A4A';
    const TEETH_COLOR = '#F5F0EB';
    const BG_GRADIENT_TOP = '#1A1D23';
    const BG_GRADIENT_BOT = '#2D3139';
    const SHIRT_COLOR = '#2B4A7A';
    const SHIRT_HIGHLIGHT = '#3B5A8A';

    function drawAvatar(timestamp) {
        const dt = state.lastTime ? (timestamp - state.lastTime) / 1000 : 0.016;
        state.lastTime = timestamp;

        const W = AVATAR_CONFIG.width;
        const H = AVATAR_CONFIG.height;
        const cx = W / 2;
        const faceY = H * 0.38;

        // Update animation state
        updateAnimations(dt);

        // Clear
        ctx.clearRect(0, 0, W, H);

        // If photo face is loaded, render photo-based avatar
        if (facePhotoLoaded && facePhoto) {
            drawPhotoAvatar(W, H, cx, faceY);
            requestAnimationFrame(drawAvatar);
            return;
        }

        // === FALLBACK: Cartoon avatar ===
        // Background gradient (professional dark)
        const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
        bgGrad.addColorStop(0, BG_GRADIENT_TOP);
        bgGrad.addColorStop(1, BG_GRADIENT_BOT);
        ctx.fillStyle = bgGrad;
        ctx.fillRect(0, 0, W, H);

        // Subtle vignette
        const vignette = ctx.createRadialGradient(cx, H * 0.4, H * 0.2, cx, H * 0.4, H * 0.8);
        vignette.addColorStop(0, 'rgba(255,255,255,0.03)');
        vignette.addColorStop(1, 'rgba(0,0,0,0.3)');
        ctx.fillStyle = vignette;
        ctx.fillRect(0, 0, W, H);

        ctx.save();
        // Apply subtle head tilt
        ctx.translate(cx, faceY);
        ctx.rotate(state.headTilt * 0.02);
        ctx.translate(-cx, -faceY);

        const breathOffset = Math.sin(state.breathCycle) * 1.5;

        // === NECK ===
        ctx.fillStyle = SKIN_SHADOW;
        ctx.beginPath();
        ctx.ellipse(cx, faceY + 85 + breathOffset, 32, 40, 0, 0, Math.PI);
        ctx.fill();

        // === SHOULDERS / SHIRT ===
        drawShoulders(cx, faceY + 110 + breathOffset, W);

        // === HAIR BACK (behind face) ===
        drawHairBack(cx, faceY);

        // === FACE (head shape) ===
        drawFace(cx, faceY + breathOffset);

        // === EARS ===
        drawEars(cx, faceY + breathOffset);

        // === HAIR FRONT ===
        drawHairFront(cx, faceY);

        // === EYES ===
        drawEyes(cx, faceY + breathOffset);

        // === NOSE ===
        drawNose(cx, faceY + 18 + breathOffset);

        // === MOUTH ===
        drawMouth(cx, faceY + 42 + breathOffset);

        // === EYEBROWS ===
        drawEyebrows(cx, faceY - 25 + breathOffset);

        ctx.restore();

        // Name tag
        drawNameTag(cx, H);

        requestAnimationFrame(drawAvatar);
    }

    // === PHOTO-BASED AVATAR RENDERING ===
    function drawPhotoAvatar(W, H, cx, faceY) {
        // Draw the face photo at ~60% of canvas height, centered, like a webcam portrait
        const imgW = facePhoto.naturalWidth;
        const imgH = facePhoto.naturalHeight;
        // Target: face takes up about 45% of canvas height (natural webcam framing)
        const targetH = H * 0.45;
        const scale = targetH / imgH;
        const drawW = imgW * scale;
        const drawH = targetH;
        const drawX = (W - drawW) / 2;
        const drawY = H - drawH;  // anchor to bottom (like sitting at desk)

        // Draw a professional background (soft gradient office look)
        const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
        bgGrad.addColorStop(0, '#2C3E50');  // Dark blue-gray top
        bgGrad.addColorStop(0.6, '#34495E');  // Slightly lighter mid
        bgGrad.addColorStop(1, '#2C3E50');  // Dark bottom
        ctx.fillStyle = bgGrad;
        ctx.fillRect(0, 0, W, H);

        // Subtle vignette effect
        const vigGrad = ctx.createRadialGradient(cx, H * 0.4, H * 0.3, cx, H * 0.4, H * 0.9);
        vigGrad.addColorStop(0, 'rgba(0,0,0,0)');
        vigGrad.addColorStop(1, 'rgba(0,0,0,0.3)');
        ctx.fillStyle = vigGrad;
        ctx.fillRect(0, 0, W, H);

        ctx.save();

        // Subtle breathing movement (shift image slightly up/down)
        const breathOffset = Math.sin(state.breathCycle) * 1.0;
        ctx.translate(0, breathOffset);

        // Subtle head tilt
        ctx.translate(cx, H * 0.45);
        ctx.rotate(state.headTilt * 0.008);
        ctx.translate(-cx, -H * 0.45);

        // Draw the photo
        ctx.drawImage(facePhoto, drawX, drawY, drawW, drawH);

        ctx.restore();

        // Name tag
        drawNameTag(cx, H);
    }

    function updateAnimations(dt) {
        // Breathing
        state.breathCycle += dt * 1.2;

        // Blinking (every 3-6 seconds)
        state.blinkTimer += dt;
        if (state.blinkState === 0 && state.blinkTimer > 3 + Math.random() * 3) {
            state.blinkState = 1;
            state.blinkTimer = 0;
        }
        if (state.blinkState === 1) {
            state.blinkTimer += dt * 8;
            if (state.blinkTimer >= 1) { state.blinkState = 2; state.blinkTimer = 0; }
        }
        if (state.blinkState === 2) {
            state.blinkTimer += dt * 6;
            if (state.blinkTimer >= 0.15) { state.blinkState = 3; state.blinkTimer = 0; }
        }
        if (state.blinkState === 3) {
            state.blinkTimer += dt * 6;
            if (state.blinkTimer >= 1) { state.blinkState = 0; state.blinkTimer = 0; }
        }

        // Eye movement (slow smooth gaze shifts)
        state.microExpressionTimer += dt;
        if (state.microExpressionTimer > 2 + Math.random() * 4) {
            state.eyeTargetX = (Math.random() - 0.5) * 6;
            state.eyeTargetY = (Math.random() - 0.5) * 3;
            state.headTiltTarget = (Math.random() - 0.5) * 1.5;
            state.microExpressionTimer = 0;
        }
        state.eyeX += (state.eyeTargetX - state.eyeX) * dt * 2;
        state.eyeY += (state.eyeTargetY - state.eyeY) * dt * 2;
        state.headTilt += (state.headTiltTarget - state.headTilt) * dt * 1.5;

        // Lip sync when speaking
        if (state.speaking) {
            state.mouthOpen = 0.3 + Math.sin(Date.now() * 0.012) * 0.25 +
                              Math.sin(Date.now() * 0.019) * 0.15 +
                              Math.sin(Date.now() * 0.007) * 0.1;
            state.mouthOpen = Math.max(0.05, Math.min(0.8, state.mouthOpen));
            state.browRaise += (0.15 - state.browRaise) * dt * 3;
        } else {
            state.mouthOpen += (0 - state.mouthOpen) * dt * 8;
            state.browRaise += (0 - state.browRaise) * dt * 3;
        }
    }

    function drawShoulders(cx, y, W) {
        // Shirt / shoulders
        const shirtGrad = ctx.createLinearGradient(cx - 160, y, cx + 160, y + 120);
        shirtGrad.addColorStop(0, SHIRT_COLOR);
        shirtGrad.addColorStop(0.5, SHIRT_HIGHLIGHT);
        shirtGrad.addColorStop(1, SHIRT_COLOR);
        ctx.fillStyle = shirtGrad;
        ctx.beginPath();
        ctx.moveTo(cx - 160, y + 120);
        ctx.quadraticCurveTo(cx - 140, y - 10, cx - 35, y);
        ctx.lineTo(cx + 35, y);
        ctx.quadraticCurveTo(cx + 140, y - 10, cx + 160, y + 120);
        ctx.lineTo(cx - 160, y + 120);
        ctx.fill();

        // Collar
        ctx.strokeStyle = '#1E3A5A';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(cx - 20, y + 2);
        ctx.quadraticCurveTo(cx, y + 12, cx + 20, y + 2);
        ctx.stroke();
    }

    function drawHairBack(cx, faceY) {
        ctx.fillStyle = HAIR_COLOR;
        ctx.beginPath();
        ctx.ellipse(cx, faceY - 20, 78, 85, 0, Math.PI, 0);
        ctx.ellipse(cx, faceY + 5, 80, 50, 0, 0, Math.PI * 0.15);
        ctx.fill();
    }

    function drawFace(cx, faceY) {
        // Main face shape — oval with slight jaw definition
        const faceGrad = ctx.createRadialGradient(cx - 10, faceY - 15, 10, cx, faceY, 75);
        faceGrad.addColorStop(0, SKIN_HIGHLIGHT);
        faceGrad.addColorStop(0.6, SKIN);
        faceGrad.addColorStop(1, SKIN_SHADOW);
        ctx.fillStyle = faceGrad;

        ctx.beginPath();
        ctx.moveTo(cx - 58, faceY - 30);
        // Forehead
        ctx.quadraticCurveTo(cx - 60, faceY - 65, cx, faceY - 70);
        ctx.quadraticCurveTo(cx + 60, faceY - 65, cx + 58, faceY - 30);
        // Cheeks
        ctx.quadraticCurveTo(cx + 62, faceY + 10, cx + 48, faceY + 38);
        // Jaw
        ctx.quadraticCurveTo(cx + 30, faceY + 65, cx, faceY + 72);
        ctx.quadraticCurveTo(cx - 30, faceY + 65, cx - 48, faceY + 38);
        ctx.quadraticCurveTo(cx - 62, faceY + 10, cx - 58, faceY - 30);
        ctx.fill();

        // Subtle cheek blush
        ctx.fillStyle = 'rgba(210, 140, 120, 0.12)';
        ctx.beginPath();
        ctx.ellipse(cx - 38, faceY + 12, 18, 10, -0.2, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.ellipse(cx + 38, faceY + 12, 18, 10, 0.2, 0, Math.PI * 2);
        ctx.fill();
    }

    function drawEars(cx, faceY) {
        [[-62, 0], [62, 0]].forEach(([ox, oy]) => {
            ctx.fillStyle = SKIN;
            ctx.beginPath();
            ctx.ellipse(cx + ox, faceY - 5 + oy, 10, 18, ox > 0 ? 0.15 : -0.15, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = SKIN_SHADOW;
            ctx.beginPath();
            ctx.ellipse(cx + ox + (ox > 0 ? -2 : 2), faceY - 5 + oy, 5, 10, 0, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    function drawHairFront(cx, faceY) {
        // Top hair with volume and texture
        const hairGrad = ctx.createLinearGradient(cx - 70, faceY - 80, cx + 70, faceY - 40);
        hairGrad.addColorStop(0, HAIR_COLOR);
        hairGrad.addColorStop(0.4, HAIR_HIGHLIGHT);
        hairGrad.addColorStop(1, HAIR_COLOR);
        ctx.fillStyle = hairGrad;

        ctx.beginPath();
        ctx.moveTo(cx - 62, faceY - 30);
        ctx.quadraticCurveTo(cx - 68, faceY - 70, cx - 30, faceY - 82);
        ctx.quadraticCurveTo(cx, faceY - 88, cx + 25, faceY - 84);
        ctx.quadraticCurveTo(cx + 65, faceY - 72, cx + 62, faceY - 30);
        // Hairline
        ctx.quadraticCurveTo(cx + 50, faceY - 50, cx + 20, faceY - 55);
        ctx.quadraticCurveTo(cx, faceY - 48, cx - 25, faceY - 55);
        ctx.quadraticCurveTo(cx - 50, faceY - 50, cx - 62, faceY - 30);
        ctx.fill();

        // Side part detail
        ctx.strokeStyle = HAIR_HIGHLIGHT;
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.4;
        ctx.beginPath();
        ctx.moveTo(cx - 15, faceY - 82);
        ctx.quadraticCurveTo(cx - 25, faceY - 65, cx - 58, faceY - 40);
        ctx.stroke();
        ctx.globalAlpha = 1;
    }

    function drawEyes(cx, faceY) {
        const eyeY = faceY - 8;
        const eyeSpacing = 24;

        // Blink amount
        let blinkFactor = 1;
        if (state.blinkState === 1) blinkFactor = 1 - state.blinkTimer;
        else if (state.blinkState === 2) blinkFactor = 0.05;
        else if (state.blinkState === 3) blinkFactor = state.blinkTimer;

        [-1, 1].forEach(side => {
            const ex = cx + side * eyeSpacing;

            // Eye white
            ctx.fillStyle = '#FAFAFA';
            ctx.beginPath();
            ctx.ellipse(ex, eyeY, 14, 9 * blinkFactor, 0, 0, Math.PI * 2);
            ctx.fill();

            if (blinkFactor > 0.15) {
                // Iris
                const irisX = ex + state.eyeX;
                const irisY = eyeY + state.eyeY;
                const irisGrad = ctx.createRadialGradient(irisX - 1, irisY - 1, 1, irisX, irisY, 7);
                irisGrad.addColorStop(0, EYE_COLOR);
                irisGrad.addColorStop(0.7, EYE_COLOR);
                irisGrad.addColorStop(1, EYE_DARK);
                ctx.fillStyle = irisGrad;
                ctx.beginPath();
                ctx.ellipse(irisX, irisY, 7, 7 * blinkFactor, 0, 0, Math.PI * 2);
                ctx.fill();

                // Pupil
                ctx.fillStyle = '#0A0A0A';
                ctx.beginPath();
                ctx.ellipse(irisX, irisY, 3.5, 3.5 * blinkFactor, 0, 0, Math.PI * 2);
                ctx.fill();

                // Eye highlight/catchlight
                ctx.fillStyle = 'rgba(255,255,255,0.85)';
                ctx.beginPath();
                ctx.ellipse(irisX + 2, irisY - 2, 2, 1.8 * blinkFactor, 0.3, 0, Math.PI * 2);
                ctx.fill();
                ctx.beginPath();
                ctx.ellipse(irisX - 1.5, irisY + 1, 0.8, 0.7 * blinkFactor, 0, 0, Math.PI * 2);
                ctx.fill();
            }

            // Upper eyelid line
            ctx.strokeStyle = '#6B5040';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.ellipse(ex, eyeY - 1, 14, 9 * blinkFactor, 0, Math.PI + 0.15, -0.15);
            ctx.stroke();

            // Eyelashes (top)
            if (blinkFactor > 0.3) {
                ctx.strokeStyle = '#3A2820';
                ctx.lineWidth = 1.2;
                ctx.beginPath();
                ctx.ellipse(ex, eyeY - 1, 15, 10 * blinkFactor, 0, Math.PI + 0.2, -0.2);
                ctx.stroke();
            }

            // Lower eyelid subtle line
            ctx.strokeStyle = 'rgba(120, 90, 70, 0.3)';
            ctx.lineWidth = 0.8;
            ctx.beginPath();
            ctx.ellipse(ex, eyeY + 1, 12, 7 * blinkFactor, 0, 0.2, Math.PI - 0.2);
            ctx.stroke();
        });
    }

    function drawNose(cx, noseY) {
        // Nose bridge shadow
        ctx.strokeStyle = 'rgba(160, 120, 90, 0.25)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(cx - 1, noseY - 20);
        ctx.quadraticCurveTo(cx - 2, noseY, cx - 6, noseY + 8);
        ctx.stroke();

        // Nose tip
        ctx.fillStyle = 'rgba(200, 160, 130, 0.4)';
        ctx.beginPath();
        ctx.ellipse(cx, noseY + 8, 7, 5, 0, 0, Math.PI * 2);
        ctx.fill();

        // Nostrils
        ctx.fillStyle = 'rgba(140, 100, 70, 0.3)';
        ctx.beginPath();
        ctx.ellipse(cx - 5, noseY + 10, 3, 2, -0.3, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.ellipse(cx + 5, noseY + 10, 3, 2, 0.3, 0, Math.PI * 2);
        ctx.fill();

        // Nose highlight
        ctx.fillStyle = 'rgba(255, 240, 220, 0.2)';
        ctx.beginPath();
        ctx.ellipse(cx + 2, noseY, 3, 8, 0.1, 0, Math.PI * 2);
        ctx.fill();
    }

    function drawMouth(cx, mouthY) {
        const openAmount = state.mouthOpen;
        const smile = state.smileAmount;

        if (openAmount > 0.05) {
            // Open mouth (speaking)
            const mouthH = 4 + openAmount * 14;
            const mouthW = 18 + smile * 4;

            // Mouth cavity
            ctx.fillStyle = '#4A1A1A';
            ctx.beginPath();
            ctx.ellipse(cx, mouthY + 2, mouthW, mouthH, 0, 0, Math.PI * 2);
            ctx.fill();

            // Teeth (top row)
            if (openAmount > 0.15) {
                ctx.fillStyle = TEETH_COLOR;
                ctx.beginPath();
                ctx.moveTo(cx - mouthW + 3, mouthY - 1);
                ctx.lineTo(cx + mouthW - 3, mouthY - 1);
                ctx.lineTo(cx + mouthW - 5, mouthY + Math.min(mouthH * 0.4, 5));
                ctx.lineTo(cx - mouthW + 5, mouthY + Math.min(mouthH * 0.4, 5));
                ctx.fill();
            }

            // Upper lip
            ctx.fillStyle = LIP_COLOR;
            ctx.beginPath();
            ctx.moveTo(cx - mouthW - 2, mouthY);
            ctx.quadraticCurveTo(cx - 6, mouthY - 5, cx, mouthY - 3);
            ctx.quadraticCurveTo(cx + 6, mouthY - 5, cx + mouthW + 2, mouthY);
            ctx.lineTo(cx + mouthW, mouthY + 1);
            ctx.quadraticCurveTo(cx, mouthY - 1, cx - mouthW, mouthY + 1);
            ctx.fill();

            // Lower lip
            ctx.fillStyle = LIP_DARK;
            ctx.beginPath();
            ctx.moveTo(cx - mouthW, mouthY + mouthH * 0.5);
            ctx.quadraticCurveTo(cx, mouthY + mouthH + 3, cx + mouthW, mouthY + mouthH * 0.5);
            ctx.quadraticCurveTo(cx, mouthY + mouthH + 1, cx - mouthW, mouthY + mouthH * 0.5);
            ctx.fill();
        } else {
            // Closed mouth — slight smile
            ctx.strokeStyle = LIP_COLOR;
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.moveTo(cx - 18, mouthY + smile * 2);
            // Cupid's bow
            ctx.quadraticCurveTo(cx - 6, mouthY - 1, cx, mouthY + 0.5);
            ctx.quadraticCurveTo(cx + 6, mouthY - 1, cx + 18, mouthY + smile * 2);
            ctx.stroke();

            // Lip color fill
            ctx.fillStyle = 'rgba(196, 122, 106, 0.35)';
            ctx.beginPath();
            ctx.moveTo(cx - 17, mouthY + smile * 1.5);
            ctx.quadraticCurveTo(cx, mouthY - 2, cx + 17, mouthY + smile * 1.5);
            ctx.quadraticCurveTo(cx, mouthY + 5, cx - 17, mouthY + smile * 1.5);
            ctx.fill();
        }
    }

    function drawEyebrows(cx, browY) {
        const raise = state.browRaise;
        const eyeSpacing = 24;

        ctx.strokeStyle = HAIR_COLOR;
        ctx.lineWidth = 2.8;
        ctx.lineCap = 'round';

        [-1, 1].forEach(side => {
            const bx = cx + side * eyeSpacing;
            ctx.beginPath();
            ctx.moveTo(bx - side * 14, browY + 3 - raise * 4);
            ctx.quadraticCurveTo(bx, browY - 5 - raise * 6, bx + side * 14, browY + 1 - raise * 3);
            ctx.stroke();
        });
    }

    function drawNameTag(cx, H) {
        const tagY = H - 36;
        // Background pill
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        const tagW = 70;
        ctx.beginPath();
        ctx.roundRect(cx - tagW, tagY, tagW * 2, 28, 14);
        ctx.fill();

        // Name text
        ctx.fillStyle = '#FFFFFF';
        ctx.font = '500 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Gneva', cx, tagY + 14);
    }

    // ===== enumerateDevices OVERRIDE =====
    // Report fake camera + mic so Teams/Zoom/Meet think hardware exists
    // and proceed to call getUserMedia (which we intercept below)
    const origEnumerateDevices = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
    navigator.mediaDevices.enumerateDevices = async function() {
        const real = await origEnumerateDevices().catch(() => []);
        // Check if camera/mic already exist
        const hasVideo = real.some(d => d.kind === 'videoinput');
        const hasAudio = real.some(d => d.kind === 'audioinput');
        const result = [...real];
        if (!hasVideo) {
            result.push({
                deviceId: 'gneva-camera', groupId: 'gneva',
                kind: 'videoinput', label: 'Gneva Virtual Camera',
                toJSON() { return { deviceId: this.deviceId, groupId: this.groupId, kind: this.kind, label: this.label }; }
            });
        }
        if (!hasAudio) {
            result.push({
                deviceId: 'gneva-mic', groupId: 'gneva',
                kind: 'audioinput', label: 'Gneva Virtual Microphone',
                toJSON() { return { deviceId: this.deviceId, groupId: this.groupId, kind: this.kind, label: this.label }; }
            });
        }
        console.log('[Gneva Avatar] enumerateDevices: reporting', result.length, 'devices (video:', result.filter(d=>d.kind==='videoinput').length, ', audio:', result.filter(d=>d.kind==='audioinput').length, ')');
        return result;
    };

    // ===== getUserMedia OVERRIDE =====
    const canvasStream = avatarCanvas.captureStream(AVATAR_CONFIG.fps);
    const avatarVideoTrack = canvasStream.getVideoTracks()[0];

    // Create a persistent audio context and destination for TTS injection
    // This is the audio stream Teams will use as "microphone"
    const gnevaAudioCtx = new AudioContext();

    // Resume AudioContext immediately (may be suspended by browser policy)
    if (gnevaAudioCtx.state === 'suspended') {
        gnevaAudioCtx.resume().then(() => {
            console.log('[Gneva Avatar] AudioContext resumed');
        });
        // Also resume on any user interaction (backup)
        ['click', 'keydown', 'mousedown', 'touchstart'].forEach(evt => {
            document.addEventListener(evt, () => {
                if (gnevaAudioCtx.state === 'suspended') gnevaAudioCtx.resume();
            }, { once: true });
        });
    }

    const gnevaAudioDest = gnevaAudioCtx.createMediaStreamDestination();
    // Create a silent oscillator to keep the stream alive
    const silentOsc = gnevaAudioCtx.createOscillator();
    const silentGain = gnevaAudioCtx.createGain();
    silentGain.gain.value = 0; // silent
    silentOsc.connect(silentGain);
    silentGain.connect(gnevaAudioDest);
    silentOsc.start();

    // Expose audio destination globally so speak() can pipe TTS audio into it
    window.__gnevaAudioCtx = gnevaAudioCtx;
    window.__gnevaAudioDest = gnevaAudioDest;

    // Start rendering
    requestAnimationFrame(drawAvatar);

    const origGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);

    navigator.mediaDevices.getUserMedia = async function(constraints) {
        const wantVideo = constraints && constraints.video;
        const wantAudio = constraints && constraints.audio;

        if (wantVideo || wantAudio) {
            const combined = new MediaStream();

            if (wantVideo) {
                console.log('[Gneva Avatar] Serving avatar video track');
                combined.addTrack(avatarVideoTrack.clone());
            }

            if (wantAudio) {
                // Give Teams our controllable audio destination instead of the real mic
                console.log('[Gneva Avatar] Serving controllable audio track (for TTS injection)');
                gnevaAudioDest.stream.getAudioTracks().forEach(t => combined.addTrack(t.clone()));
            }

            if (combined.getTracks().length > 0) {
                console.log('[Gneva Avatar] getUserMedia intercepted — tracks:', combined.getTracks().length);
                return combined;
            }
        }
        // Fallback
        return origGetUserMedia(constraints);
    };

    // Also override older API
    if (navigator.getUserMedia) {
        navigator.getUserMedia = function(constraints, success, error) {
            navigator.mediaDevices.getUserMedia(constraints).then(success).catch(error);
        };
    }

    // Expose speaking control globally
    window.__gnevaAvatar = {
        startSpeaking: function() { state.speaking = true; },
        stopSpeaking: function() { state.speaking = false; },
        setSpeaking: function(v) { state.speaking = !!v; },
        getState: function() { return Object.assign({}, state); },
    };

    console.log('[Gneva Avatar] Avatar system initialized — canvas stream ready');
})();
""".replace("__FACE_B64_PLACEHOLDER__", face_b64_js)
    return js


def get_speaking_js(speaking: bool) -> str:
    """Return JS to toggle lip-sync animation."""
    if speaking:
        return "if(window.__gnevaAvatar) window.__gnevaAvatar.startSpeaking();"
    else:
        return "if(window.__gnevaAvatar) window.__gnevaAvatar.stopSpeaking();"
