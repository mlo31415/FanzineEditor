from datetime import datetime

from FTP import FTP
from Log import Log

class FTPLog:
    g_ID: str|None =None
    g_Logfilename: str|None=None
    g_pendinglist: [str]=[]

    @staticmethod
    def Init(id: str, logfilename: str) -> None:
        FTPLog.g_ID=id
        FTPLog.g_Logfilename=logfilename

    @staticmethod
    def Timestamp() -> str:
        return f"<itemdatetime>{datetime.now().strftime("%A %B %d, %Y  %I:%M:%S %p")} EST</itemdatetime>"

    @staticmethod
    def Tagstring() -> str:
        return f"<id>{FTPLog.g_ID}</id> {FTPLog.Timestamp()}"

    @staticmethod
    def Flush():
        items="".join(FTPLog.g_pendinglist).strip(" ")
        if items != "":
            FTP().AppendString(FTPLog.g_Logfilename, items)
        FTPLog.g_pendinglist=[]

    @staticmethod
    def AppendItem(txt: str, Flush: bool=False) -> None:
        Log(f"AppendItem: {txt=}")
        FTPLog.g_pendinglist.append(f"<item>{txt.strip()}{FTPLog.Tagstring()}/item>\n")
        if Flush:
            FTPLog.Flush()

    @staticmethod
    def AppendItemVerb(verb: str, txt: str, Flush: bool=False) -> None:
        Log(f"AppendItem: {verb=} {txt=}")
        FTPLog.g_pendinglist.append(f"<item><verb>{verb}</verb>{txt.strip()}{FTPLog.Tagstring()}</item>\n\n")
        if Flush:
            FTPLog.Flush()
