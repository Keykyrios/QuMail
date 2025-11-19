import json
import logging
import os
import hashlib
import httpx
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage

log = logging.getLogger(__name__)


def hash_to_uid(value: str) -> int:
    digest = hashlib.sha256(value.encode()).digest()
    uid = int.from_bytes(digest[:4], "big")
    return uid or 1


class AgoraWidget(QWebEngineView):
    call_joined = pyqtSignal(str)
    call_left = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    media_ready = pyqtSignal(bool, bool)
    connection_state = pyqtSignal(str)

    def __init__(self, app_id: str, token_endpoint: str, parent=None):
        super().__init__(parent)
        self.app_id = app_id
        self.token_endpoint = token_endpoint
        self.current_user = ""
        self.web_view = self
        page = QWebEnginePage()
        self.setPage(page)
        self.channel = QWebChannel()
        self.channel.registerObject("agoraBridge", self)
        page.setWebChannel(self.channel)
        page.loadFinished.connect(self._on_loaded)
        self.setHtml(self._basic_html())

    def _basic_html(self) -> str:
        return (
            """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset=\"utf-8\" />
                <title>QuMail Agora</title>
                <script src=\"https://download.agora.io/sdk/release/AgoraRTC_N-4.20.2.js\"></script>
                <script src=\"qrc:///qtwebchannel/qwebchannel.js\"></script>
                <style>
                  body { margin: 0; background: #111; color: #eee; font-family: sans-serif; }
                  #local, #remote { width: 100%; height: 100%; object-fit: cover; }
                  #container { display: grid; grid-template-rows: 1fr 1fr; height: 100vh; }
                </style>
            </head>
            <body>
              <div id=\"container\">
                <div id=\"local-container\"></div>
                <div id=\"remote-container\"></div>
              </div>
              <script>
                const state = { client: null, localTrackA: null, localTrackV: null, uid: null, joined: false };
                async function joinAgora(appId, channel, token, uid, withVideo) {
                  try {
                    state.client = AgoraRTC.createClient({ mode: 'rtc', codec: 'vp8' });
                    await state.client.join(appId, channel, token || null, uid);
                    state.uid = uid; state.joined = true;
                    // local tracks
                    state.localTrackA = await AgoraRTC.createMicrophoneAudioTrack();
                    let tracks = [state.localTrackA];
                    if (withVideo) {
                      state.localTrackV = await AgoraRTC.createCameraVideoTrack();
                      tracks.push(state.localTrackV);
                      const localPlayer = document.createElement('div');
                      localPlayer.id = 'local-player';
                      document.getElementById('local-container').appendChild(localPlayer);
                      state.localTrackV.play('local-container');
                    }
                    await state.client.publish(tracks);
                    // remote subscribe
                    state.client.on('user-published', async (user, mediaType) => {
                      await state.client.subscribe(user, mediaType);
                      if (mediaType === 'video') {
                        const remoteId = 'remote-' + user.uid;
                        let container = document.getElementById(remoteId);
                        if (!container) {
                          container = document.createElement('div');
                          container.id = remoteId;
                          document.getElementById('remote-container').appendChild(container);
                        }
                        user.videoTrack.play(container);
                      }
                      if (mediaType === 'audio') {
                        user.audioTrack.play();
                      }
                    });
                    window.pyqtwebchannel.send({ type: 'joined', data: { channel } });
                  } catch (e) {
                    window.pyqtwebchannel.send({ type: 'error', data: { message: e.message } });
                  }
                }
                async function leaveAgora() {
                  try {
                    if (state.localTrackA) state.localTrackA.close();
                    if (state.localTrackV) state.localTrackV.close();
                    if (state.client) await state.client.leave();
                    window.pyqtwebchannel.send({ type: 'left', data: {} });
                  } catch (e) {
                    window.pyqtwebchannel.send({ type: 'error', data: { message: e.message } });
                  }
                }
                function toggleMute() {
                  try {
                    if (state.localTrackA) { state.localTrackA.setEnabled(!state.localTrackA.enabled); }
                  } catch(e) { window.pyqtwebchannel.send({ type: 'error', data: { message: e.message } }); }
                }
                function toggleVideo() {
                  try {
                    if (state.localTrackV) { state.localTrackV.setEnabled(!state.localTrackV.enabled); }
                  } catch(e) { window.pyqtwebchannel.send({ type: 'error', data: { message: e.message } }); }
                }
                window.agoraClient = { joinAgora, leaveAgora, toggleMute, toggleVideo };
                window.pyqtwebchannel = { send: function(message){ try{ if (window.agoraBridge && window.agoraBridge.handle_js_message) { window.agoraBridge.handle_js_message(JSON.stringify(message)); } } catch(e){} } };
              </script>
            </body>
            </html>
            """
        )

    def _on_loaded(self, ok: bool):
        if ok:
            log.info("Agora page loaded")
        else:
            log.error("Agora page failed to load")

    def set_current_user(self, user_id: str):
        self.current_user = user_id

    async def join(self, channel_name: str, uid_source: str, with_video: bool):
        uid = hash_to_uid(uid_source)
        token = ''  # App ID only mode by default
        # If a token endpoint is configured, try to get a token; otherwise proceed tokenless
        if self.token_endpoint:
            try:
                fetched = await self._get_token(channel_name, uid)
                if fetched:
                    token = fetched
            except Exception:
                pass
        js = f"window.agoraClient.joinAgora('{self.app_id}', '{channel_name}', '{token}', {uid}, {str(with_video).lower()});"
        self.page().runJavaScript(js)

    async def leave(self):
        self.page().runJavaScript("window.agoraClient.leaveAgora();")

    def toggle_mute(self):
        self.page().runJavaScript("window.agoraClient.toggleMute();")

    def toggle_video(self):
        self.page().runJavaScript("window.agoraClient.toggleVideo();")

    async def _get_token(self, channel_name: str, uid: int) -> str:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.token_endpoint, json={
                    "appId": self.app_id,
                    "channelName": channel_name,
                    "uid": uid,
                    "expireSeconds": 3600
                })
                resp.raise_for_status()
                data = resp.json()
                return data.get("token", "")
        except Exception as e:
            log.error(f"Failed to get Agora token: {e}")
            return ""

    def handle_js_message(self, message_json: str):
        try:
            message = json.loads(message_json)
            t = message.get('type')
            if t == 'joined':
                self.call_joined.emit(message['data'].get('channel', ''))
            elif t == 'left':
                self.call_left.emit("")
            elif t == 'error':
                self.error_occurred.emit(message['data'].get('message', ''))
        except Exception as e:
            log.error(f"Error from Agora JS: {e}")


