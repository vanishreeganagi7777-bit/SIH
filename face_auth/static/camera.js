let cameraStream;
const $ = (id) => document.getElementById(id);

function setStatus(message, kind = '') {
  const status = $('status');
  status.textContent = message;
  status.className = `status ${kind}`;
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus('Camera API is unavailable. Open this app at http://127.0.0.1:5000 or HTTPS, not as a local file or an insecure network URL.', 'error');
    return false;
  }
  if (!window.isSecureContext && !['localhost', '127.0.0.1'].includes(window.location.hostname)) {
    setStatus('Camera access requires HTTPS. Open the app through HTTPS or use http://127.0.0.1:5000 on this computer.', 'error');
    return false;
  }
  try {
    cameraStream?.getTracks().forEach(track => track.stop());
    cameraStream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'user', width: {ideal: 720}, height: {ideal: 540}}, audio: false});
    $('camera').srcObject = cameraStream;
    await $('camera').play();
    $('cameraHint').textContent = 'Camera ready - keep one face in frame';
    return true;
  } catch (error) {
    // Some desktop cameras do not advertise a front-facing mode. Retry with
    // the browser's default video device before treating it as a failure.
    if (error.name === 'OverconstrainedError' || error.name === 'NotFoundError') {
      try {
        cameraStream = await navigator.mediaDevices.getUserMedia({video: true, audio: false});
        $('camera').srcObject = cameraStream;
        await $('camera').play();
        $('cameraHint').textContent = 'Camera ready - keep one face in frame';
        return true;
      } catch (fallbackError) { error = fallbackError; }
    }
    const messages = {
      NotAllowedError: 'Camera permission is blocked. Select the lock icon beside the address, allow Camera, then reload the page. Also check Windows Settings > Privacy & security > Camera.',
      NotReadableError: 'The camera is already being used by another app. Close Teams, Zoom, Camera, or other browser tabs and try again.',
      NotFoundError: 'No camera was detected. Connect or enable a camera, then reload the page.',
      OverconstrainedError: 'No compatible camera was found. Check that your webcam is connected and enabled.',
    };
    setStatus(messages[error.name] || `Unable to start the camera (${error.name || 'unknown error'}).`, 'error');
    return false;
  }
}

function captureFrame() {
  const video = $('camera');
  if (!video.videoWidth) throw new Error('Start the camera before capturing.');
  const canvas = document.createElement('canvas');
  canvas.width = 640; canvas.height = 480;
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', .9);
}

const pause = (milliseconds) => new Promise(resolve => setTimeout(resolve, milliseconds));
function cameraCleanup() { cameraStream?.getTracks().forEach(track => track.stop()); }
window.addEventListener('pagehide', cameraCleanup);

function setupRegistration() {
  const samples = [];
  const capture = $('capture');
  $('startCamera').addEventListener('click', async () => { if (await startCamera()) capture.disabled = false; });
  capture.addEventListener('click', () => {
    try {
      if (samples.length === 8) return;
      const image = captureFrame(); samples.push(image);
      const thumbnail = new Image(); thumbnail.src = image; thumbnail.alt = `Face sample ${samples.length}`; $('samples').append(thumbnail);
      $('sampleCount').textContent = `(${samples.length}/3)`;
      $('submit').disabled = samples.length < 3;
      setStatus(samples.length < 3 ? `Sample ${samples.length} captured. Capture ${3 - samples.length} more.` : `${samples.length} samples ready.`, 'ok');
    } catch (error) { setStatus(error.message, 'error'); }
  });
  $('registerForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!$('consent').checked) return setStatus('Consent is required to register.', 'error');
    const button = $('submit'); button.disabled = true; setStatus('Registering your face...');
    try {
      const response = await fetch('/register', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({officialId: $('officialId').value, fullName: $('fullName').value, designation: $('designation').value, images: samples})});
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.message || 'Registration failed.');
      setStatus(result.message, 'ok'); cameraCleanup(); setTimeout(() => location.assign(result.redirect), 600);
    } catch (error) { button.disabled = false; setStatus(error.message, 'error'); }
  });
}

function setupLogin() {
  const signIn = $('signIn');
  $('startCamera').addEventListener('click', async () => { if (await startCamera()) signIn.disabled = false; });
  signIn.addEventListener('click', async () => {
    signIn.disabled = true; setStatus('Verification 1 of 3: look straight ahead.');
    try {
      const images = [captureFrame()];
      setStatus('Verification 2 of 3: stay centred.'); await pause(500); images.push(captureFrame());
      setStatus('Verification 3 of 3: stay centred.'); await pause(500); images.push(captureFrame());
      setStatus('Checking your three face samples...');
      const response = await fetch('/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({images})});
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.message || 'Sign-in failed.');
      setStatus('Login successful.', 'ok'); cameraCleanup(); setTimeout(() => location.assign(result.redirect), 350);
    } catch (error) { signIn.disabled = false; setStatus(error.message, 'error'); }
  });
}
