"""
A fake FTP server for Tier 1 tests.

FanzinesEditor's FTP class does all its work through one ftplib connection object, FTP.g_ftp, using a dozen calls
(cwd, pwd, mkd, nlst, delete, rmd, rename, storbinary, retrbinary, size). FakeServer provides those calls with the
"server" held in memory, and Install() puts it in place of the real connection. So everything above that -- FE's own
FTP code (FileExists, SetDirectory, BackupServerFile, CopyAndRenameFile, VerifyUploadedSize, ...) and all of FE --
runs unchanged, without touching the network.

Failures can be injected at this lowest level, so FE sees exactly what it would from a real server:
    server.Fail("stor", lambda path: path.endswith("/x.pdf"))     # that upload is refused
Operations: "cwd", "mkd", "delete", "rmd", "rename", "stor", "retr", "size".
"""
from __future__ import annotations

import posixpath
from ftplib import error_perm
from typing import Callable


class FakeServer:
    def __init__(self) -> None:
        self.Files: dict[str, bytes]={}     # Full path -> contents
        self.Dirs: set[str]={"/"}
        self._cwd="/"
        self._failures: list[tuple[str, Callable[[str], bool]]]=[]

    # ---------------------------------------------- helpers for the tests
    def Fail(self, operation: str, when: Callable[[str], bool]) -> None:
        self._failures.append((operation, when))

    def ClearFailures(self) -> None:
        self._failures=[]

    def Put(self, path: str, data: bytes|str) -> None:
        """Put a file on the server, creating its directories."""
        path=self._abs(path)
        self._makedirs(posixpath.dirname(path))
        self.Files[path]=data.encode("utf-8") if isinstance(data, str) else data

    def Get(self, path: str) -> bytes|None:
        return self.Files.get(self._abs(path))

    def GetText(self, path: str) -> str|None:
        data=self.Get(path)
        return None if data is None else data.decode("utf-8")

    def Exists(self, path: str) -> bool:
        path=self._abs(path)
        return path in self.Files or path in self.Dirs

    def Listing(self, directory: str) -> list[str]:
        d=self._abs(directory)
        return sorted({posixpath.basename(p) for p in list(self.Files)+list(self.Dirs) if p != d and posixpath.dirname(p) == d})

    # ---------------------------------------------- internals
    def _abs(self, path: str) -> str:
        path=path.strip().replace("//", "/")
        if not path.startswith("/"):
            path=posixpath.join(self._cwd, path)
        path=posixpath.normpath(path)
        return "/" if path in ("", ".", "//") else path

    def _makedirs(self, d: str) -> None:
        while d not in self.Dirs:
            self.Dirs.add(d)
            d=posixpath.dirname(d)

    def _fails(self, operation: str, path: str) -> bool:
        return any(op == operation and when(path) for op, when in self._failures)

    # ---------------------------------------------- the ftplib calls FE's FTP class makes
    def cwd(self, d: str) -> str:
        p=self._abs(d)
        if p not in self.Dirs or self._fails("cwd", p):
            raise error_perm(f"550 Can't change directory to {d}: No such file or directory")
        self._cwd=p
        return f"250 OK. Current directory is {p}"

    def pwd(self) -> str:
        return self._cwd

    def mkd(self, d: str) -> str:
        p=self._abs(d)
        if posixpath.dirname(p) not in self.Dirs or p in self.Files or self._fails("mkd", p):
            raise error_perm(f"550 Can't create directory: {d}")
        self.Dirs.add(p)
        return f'257 "{p}" : The directory was successfully created'

    def nlst(self, *args) -> list[str]:
        return self.Listing(args[0] if args else self._cwd)

    def delete(self, f: str) -> str:
        p=self._abs(f)
        if p not in self.Files or self._fails("delete", p):
            raise error_perm(f"550 Could not delete {f}: No such file or directory")
        del self.Files[p]
        return f"250 Deleted {f}"

    def rmd(self, d: str) -> str:
        p=self._abs(d)
        if p not in self.Dirs or p == "/" or self.Listing(p) or self._fails("rmd", p):
            raise error_perm(f"550 Can't remove directory: {d}")
        self.Dirs.discard(p)
        return "250 The directory was successfully removed"

    def rename(self, old: str, new: str) -> str:
        po, pn=self._abs(old), self._abs(new)
        if po not in self.Files or posixpath.dirname(pn) not in self.Dirs or self._fails("rename", po) or self._fails("rename", pn):
            raise error_perm(f"550 Rename/move failure: {old}")
        self.Files[pn]=self.Files.pop(po)      # (Like the real server, this replaces an existing file of the new name)
        return "250 File successfully renamed or moved"

    def storbinary(self, cmd: str, fp, *args, **kwargs) -> str:
        verb, name=cmd.split(" ", 1)
        p=self._abs(name)
        if posixpath.dirname(p) not in self.Dirs:
            raise error_perm(f"553 Can't open that file: No such file or directory")
        if self._fails("stor", p):
            return "550 Simulated upload failure"
        data=fp.read()
        self.Files[p]=(self.Files.get(p, b"") if verb == "APPE" else b"")+data
        return "226-File successfully transferred\n226 0.001 seconds"

    def retrbinary(self, cmd: str, callback, *args, **kwargs) -> str:
        p=self._abs(cmd.split(" ", 1)[1])
        if p not in self.Files or self._fails("retr", p):
            raise error_perm(f"550 Can't open {p}: No such file or directory")
        callback(self.Files[p])
        return "226-File successfully transferred\n226 0.001 seconds"

    def size(self, name: str) -> int:
        p=self._abs(name)
        if p not in self.Files:
            raise error_perm(f"550 Could not get file size: {name}")
        return 0 if self._fails("size", p) else len(self.Files[p])     # (A "size" failure looks like a truncated upload)

    def quit(self) -> str:
        return "221 Goodbye."

    def close(self) -> None:
        pass


# Put a fresh FakeServer in place of FE's FTP connection, and make sure nothing can reconnect to the real one
def Install() -> FakeServer:
    import FTP as ftpmodule
    server=FakeServer()
    ftpmodule.FTP.g_ftp=server
    ftpmodule.FTP.g_curdirpath="/"
    ftpmodule.FTP.g_credentials={"ID": "test", "PW": ""}
    ftpmodule.FTP._lastMessage=""
    ftpmodule.FTP.Reconnect=lambda self: True
    ftpmodule.FTP.OpenConnection=lambda self, credentialsFilePath: True
    return server
