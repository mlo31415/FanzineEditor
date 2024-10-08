from datetime import datetime

from FTP import FTP

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
        return f"<datetime>{datetime.now().strftime("%A %B %d, %Y  %I:%M:%S %p")} EST</datetime>"

    @staticmethod
    def Tagstring() -> str:
        return f"<id>{FTPLog.g_ID}</id> {FTPLog.Timestamp()}"

    @staticmethod
    def Flush():
        items="\n".join(FTPLog.g_pendinglist)
        FTP().AppendString(FTPLog.g_Logfilename, items)

    @staticmethod
    def AppendRawTextStringImmediate(lines: str) -> None:
        FTP().AppendString(FTPLog.g_Logfilename, f"<item>{FTPLog.Tagstring()}<rawtext>{lines}</rawtext></item>\n")
    @staticmethod
    def AppendRawTextString(lines: str) -> None:
        FTPLog.g_pendinglist.append(f"<item>{FTPLog.Tagstring()}<rawtext>{lines}</rawtext></item>\n")

    @staticmethod
    def AppendItemImmediate(txt: str) -> None:
        FTP().AppendString(FTPLog.g_Logfilename, f"<item>{FTPLog.Tagstring()}<txt>{txt}</txt></item>\n")
    @staticmethod
    def AppendItem(txt: str) -> None:
        FTPLog.g_pendinglist.append(f"<item>{FTPLog.Tagstring()}<txt>{txt}</txt></item>\n")