"""Per-user desktop ownership and activation through Qt's local IPC."""
from pathlib import Path
import hashlib
import ctypes
import sys

from PyQt6.QtCore import QObject, QLockFile, QStandardPaths, QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


class DesktopInstance(QObject):
    activated = pyqtSignal()

    def __init__(self, directory=None):
        super().__init__()
        root = Path(directory or QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.GenericConfigLocation)) / "NeuCockpit"
        root.mkdir(parents=True, exist_ok=True)
        self._name = "neucockpit-" + hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:24]
        self._lock = QLockFile(str(root / "desktop.lock"))
        self._lock.setStaleLockTime(0)  # A slow startup must never expire a live owner's lock.
        self._server = None
        self._event = None
        if sys.platform == "win32":
            self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self._kernel.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
            self._kernel.CreateEventW.restype = ctypes.c_void_p
            self._kernel.SetEvent.argtypes = [ctypes.c_void_p]
            self._kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            self._kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            self._event = self._kernel.CreateEventW(None, False, False, "Local\\" + self._name)
            if not self._event:
                raise ctypes.WinError(ctypes.get_last_error())
            self._timer = QTimer(self)
            self._timer.setInterval(100)
            self._timer.timeout.connect(self._poll_activation)
        else:
            self._server = QLocalServer(self)
            self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
            self._server.newConnection.connect(self._accept)

    def acquire(self):
        if not self._lock.tryLock(0):
            if self._lock.error() != QLockFile.LockError.LockFailedError:
                raise RuntimeError("Cannot access the desktop instance lock")
            if self._event:
                self._kernel.SetEvent(self._event)
                return False
            socket = QLocalSocket(self)
            socket.connectToServer(self._name)
            if socket.waitForConnected(1500):
                socket.write(b"activate\n")
                socket.waitForBytesWritten(1000)
            socket.abort()
            socket.deleteLater()
            return False
        if self._event:
            self._timer.start()
            return True
        QLocalServer.removeServer(self._name)
        if not self._server.listen(self._name):
            self._lock.unlock()
            raise RuntimeError(self._server.errorString())
        return True

    def _poll_activation(self):
        if self._event and self._kernel.WaitForSingleObject(self._event, 0) == 0:
            self.activated.emit()

    def _accept(self):
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.disconnected.connect(socket.deleteLater)
            socket.disconnectFromServer()
            self.activated.emit()

    def close(self):
        if self._server is not None:
            self._server.close()
        if self._event:
            self._timer.stop()
            self._kernel.CloseHandle(self._event)
            self._event = None
        self._lock.unlock()
