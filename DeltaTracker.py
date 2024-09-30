from __future__ import annotations

from datetime import datetime
import os

from FTP import FTP


# These classes track changes to the list of files for a particular Con Instance
# All it cares about is the files and their names
# Once the user is done editing the ConInstance page and does an upload, this class will provide the instructions
#   for the upload so that all the accumulated edits get up there.

class Delta:
    def __init__(self, verb: str, sourceFilename: str, sourcePath: str="", newSourceFilename: str=""):
        self.Verb: str=verb     # Verb is add, rename, delete, replace
        self.SourceFilename: str=sourceFilename     # The name of the file
        self.SourcePath: str=sourcePath     # The path (no filename) of the file on the local disk
        self.NewSourceFilename: str=newSourceFilename       # A new name for the file on the server (needed only for a rename)
        self.Uploaded: bool=False       # As an upload proceeds, successful deltas are flagged as uploaded, so if it fails later and the upload is re-run, it isn't duplicated


    def __str__(self) -> str:
        s=self.Verb+": "+self.SourceFilename
        if self.NewSourceFilename is not None and len(self.NewSourceFilename) > 0:
            s+=" NewSourceFilename="+self.NewSourceFilename
        return s


# Changes (the tuple providing info needed to defined them) are (in the order in which they must be executed):
#       Delete a file which exists on the website ("delete", con, "")
#       Rename an existing website file ("rename", con, oldname)
#       Add a new file ("add", con, "")
#       Replace an existing file ("replace", con, oldname)
# When two deltas affect the same file, they are usually merged.  (E.g., Add followed by Delete cancels out; Add followed by Rename updates the Add with the new name.)
class DeltaTracker:
    def __init__(self):
        self._deltas: list[Delta]=list()

    def __str__(self) -> str:
        if self._deltas is None or len(self._deltas) == 0:
            return ""
        s=""
        for d in self._deltas:
            s+=">>"+str(d)+"\n"
        return s

    def Add(self, sourceFilepathname: str) -> None:
        path, filename=os.path.split(sourceFilepathname)
        self._deltas.append(Delta("add", filename, sourcePath=path))


    def Delete(self, sourceFilename: str) -> None:
        # If the item being deleted was just added, simply remove the add from the deltas list
        for i, item in enumerate(self._deltas):
            if item.Verb == "add":
                if item.SourceFilename == sourceFilename:
                    del self._deltas[i]
                    return

        # OK, the item is not queued to be added, so it must already be on the website: add a delete action to the deltas list
        self._deltas.append(Delta("delete", sourceFilename))


    # Change the filename of a file. It may be on the server already or yet to be added.
    def Rename(self, sourceFilename: str, newname: str) -> None:
        # If the old and new names are gthe same, we'd done.
        if sourceFilename == newname:
            return

        # First check to see if this is a rename of a rename.  If it is, merge them by replacing the existing rename.
        for item in self._deltas:
            if item.Verb == "rename":
                if item.SourceFilename == sourceFilename:
                    item.NewSourceFilename=newname
                    return

        # Now check to see if this is a rename of a file that is on the delta list to be added.  If so, we just modify the add Delta
        for item in self._deltas:
            if item.Verb == "add":
                if item.SourceFilename == sourceFilename:
                    item.NewSourceFilename=newname  # Now it will get renamed in the process of being added
                    return

        # If it doesn't match anything in the delta list, then it must be a rename of an existing file.
        self._deltas.append(Delta("rename", sourceFilename, newSourceFilename=newname))


    # We want to replace one file on the server with another, leaving the rest of the data unchanged
    # This will cause a new upload and may change the name of the pdf on the server
    def Replace(self, oldSourceFilename: str, newfilepathname: str):
        newfilepath, newfilename=os.path.split(newfilepathname)
        # Check to see if the replacement is in a row already scheduled to be renamed.
        for i, item in enumerate(self._deltas):
            if item.Verb == "rename" and item.SourceFilename == oldSourceFilename:
                # This is a bit ugly, as it's not completely clear what is intended.
                # First, the user elected to change an existing filename on the server and later decided to replace it by uploading a new file.
                # Question: Is the new file supposed to be given the new name, also?  It's hard to see why, so we'll change this to:
                # Upload the new file
                self.Add(newfilepathname)
                # Delete the old file
                self.Delete(oldSourceFilename)
                # Delete the rename request
                del self._deltas[i]
                return

        # Check to see if this is a replacement of a file scheduled to be added
        for item in self._deltas:
            if item.Verb == "add" and item.SourceFilename == oldSourceFilename:
                # Just update the local pathname in the add entry
                item.SourceFilename=newfilename
                return

        # If it doesn't match anything in the delta list, then it must be a new local file to replace the server file in an existing entry
        # Delete the old server file and add the new
        self.Add(newfilepathname)
        # Delete the old file
        self.Delete(oldSourceFilename)



    @property
    def Num(self) -> int:
        return len(self._deltas)

    @property
    def Deltas(self) -> list[Delta]:
        return self._deltas


class UpdateFTPLog:
    g_ID: str|None=None

    @staticmethod
    def Init(id: str):
        UpdateFTPLog.g_ID=id
        pass


    @staticmethod
    def Log(series: str, con: str = "", deltas: Delta|None = None):
        lines="Uploaded ConInstance: "+series+":"+con+"   "+"["+UpdateFTPLog.g_ID+"  "+datetime.now().strftime("%A %B %d, %Y  %I:%M:%S %p")+" EST]\n"
        if deltas is not None:
            lines+="^^deltas by "+FTP.GetEditor()+":\n"+str(deltas)+"\n"
        FTP().AppendString("/updatelog.txt", lines)
        pass


    @staticmethod
    def LogText(txt: str):
        FTP().AppendString("/updatelog.txt", txt+"   ["+UpdateFTPLog.g_ID+"  "+FTP.GetEditor()+"  "+datetime.now().strftime("%A %B %d, %Y  %I:%M:%S %p")+" EST]\n")