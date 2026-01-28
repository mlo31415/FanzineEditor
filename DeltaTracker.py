from __future__ import annotations

from datetime import datetime
import os

from FTP import FTP
from FanzineIndexPageTableRow import FanzineIndexPageTableRow


# These classes track changes to the list of files for a particular Con Instance
# All it cares about is the files and their names
# Once the user is done editing the ConInstance page and does an upload, this class will provide the instructions
#   for the upload so that all the accumulated edits get up there.

class Delta:
    def __init__(self, verb: str, serverDirName: str, row: FanzineIndexPageTableRow=None) -> None:
        self.Verb: str=verb     # Verb is add, rename, delete, replace
        self.Row: FanzineIndexPageTableRow=row
        self.ServerDirName: str|None=serverDirName

        self.ServerFilename: str|None=None
        self.SourceFilename: str|None=None     # The name of the file to be operated on (needed for all)
        self.SourcePath: str|None=None     # The path (no filename) of the file on the local disk (needed only for add and replace)
        self.NewFilename: str|None=None       # The new name for the file on the server (needed only for a rename)
        self.OldFilename: str|None=None       # The new fileename. Used in a replace
        self.Uploaded: bool=False       # As an upload proceeds, successful deltas are flagged as uploaded, so if it fails later and the upload is re-run, it isn't duplicated


class DeltaAdd(Delta):
    def __init__(self, SourcePath: str|None=None, serverDirName: str|None=None, row: FanzineIndexPageTableRow=None) -> None:
        # The filename to be loaded and the issuename to be used comes from Row to allow for later editing by the user
        Delta.__init__(self, "add", serverDirName, row)
        self.SourcePath=SourcePath

    def __str__(self) -> str:
        s="Add: "+self.SourceFilename
        if self.ServerDirName is not None and len(self.ServerDirName) > 0:
            s+=" ServerDirName="+self.ServerDirName
        return s

class DeltaReplace(Delta):
    def __init__(self, SourcePath: str|None=None, serverDirName: str|None=None, NewSourceFilename: str|None=None, OldFilename: str|None=None, row: FanzineIndexPageTableRow=None) -> None:
        # This is basically just an Add with some addition information for logging purposes
        # The filename to be loaded and the issuename to be used comes from Row to allow for later editing by the user
        Delta.__init__(self, "replace", serverDirName, row)
        self.oldServerFilename=row.Cells[0]   # The name of the file being replaced
        self.SourcePath=SourcePath
        self.NewSourceFilename=NewSourceFilename
        self.OldFilename=OldFilename

    def __str__(self) -> str:
        s="Replace: "+self.SourceFilename
        if self.NewSourceFilename is not None and len(self.NewSourceFilename) > 0:
            s+=" NewSourceFilename="+self.NewSourceFilename
        return s

class DeltaDelete(Delta):
    def __init__(self, serverDirName: str|None=None, row: FanzineIndexPageTableRow=None) -> None:
        Delta.__init__(self, "delete", serverDirName, row)
        self.ServerFilename=row.Cells[0]

    def __str__(self) -> str:
        s="Delete: "+self.SourceFilename
        if self.ServerDirName is not None and len(self.ServerDirName) > 0:
            s+=" ServerDirName="+self.ServerDirName
        return s


class DeltaRename(Delta):
    def __init__(self, OldFilename: str|None=None, serverDirName: str|None=None, row: FanzineIndexPageTableRow=None):
        Delta.__init__(self, "rename", serverDirName, row)
        self.OldFilename=OldFilename

    def __str__(self) -> str:
        s="Rename: "+self.OldFilename
        if self.NewFilename is not None and len(self.NewFilename) > 0:
            s+=" NewFilename="+self.Row.Cells[1]
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

    def Add(self, sourceFilepathname: str, row: FanzineIndexPageTableRow=None, serverDirName: str="") -> None:
        path, _=os.path.split(sourceFilepathname)
        self._deltas.append(DeltaAdd(SourcePath=path, serverDirName=serverDirName, row=row))


    def Delete(self, serverDirName: str="", row: FanzineIndexPageTableRow=None) -> None:
        # If the item being deleted was just added, simply remove the add from the deltas list
        for i, item in enumerate(self._deltas):
            if item.Verb == "add":
                if item.Row.Cells[0] == row.Cells[0]:
                    del self._deltas[i]
                    return

        # OK, the item is not queued to be added, so it must already be on the website: add a delete action to the deltas list
        self._deltas.append(DeltaDelete(serverDirName=serverDirName, row=row))


    # Change the filename of a file. It may be on the server already or yet to be added.
    def Rename(self, sourceFilename: str, newname: str="", serverDirName: str="", row: FanzineIndexPageTableRow=None) -> None:
        # If the old and new names are the same, we're done.
        if sourceFilename == newname:
            return

        # First check to see if this is a rename of a rename.  If it is, merge them by replacing the existing rename.
        for item in self._deltas:
            if item.Verb == "rename":
                if item.Row.Cells[0] == row.Cells[0]:        # Is the *old* filename for this rename the same as the *new* filename for a previous one
                    return

        # Now check to see if this is a rename of a file that is on the delta list to be added.
        # If so, we're done since the new name will be taken from the row
        for item in self._deltas:
            if item.Verb == "add":
                if item.Row.Cells[0] == sourceFilename:
                    return

        # If it doesn't match anything in the delta list, then it must be a rename of an existing file.
        # The currewnt name of the existing file will be pulled from the row
        self._deltas.append(DeltaRename(OldFilename=sourceFilename, serverDirName=serverDirName, row=row))


    # We want to replace one file on the server with another, leaving the rest of the data unchanged
    # This will cause a new upload and may change the name of the pdf on the server
    def Replace(self, oldSourceFilename: str="", newfilepathname: str="", row: FanzineIndexPageTableRow|None=None, serverDirName: str=""):
        newfilepath, newfilename=os.path.split(newfilepathname)
        # Check to see if the replacement is in a row already scheduled to be renamed.
        for i, item in enumerate(self._deltas):
            if item.Verb == "rename" and item.SourceFilename == oldSourceFilename:
                # This is a bit ugly, as it's not completely clear what is intended.
                # First, the user elected to change an existing filename on the server and later decided to replace it by uploading a new file.
                # Question: Is the new file supposed to be given the new name, also?  It's hard to see why, so we'll change this to:
                # Upload the new file
                self.Add(newfilepathname, row=row)
                # Delete the old file
                self.Delete(oldSourceFilename, row.Cells[1])
                # Delete the rename request
                del self._deltas[i]
                return

        # Check to see if this is a replacement of a file already scheduled to be added
        for item in self._deltas:
            if item.Verb == "add" and item.SourceFilename == oldSourceFilename:
                # Just update the local pathname to the new file in the add entry
                item.SourceFilename=newfilename
                return

        # If it doesn't match anything in the delta list, then it must be a new local file to replace the server file in an existing entry
        # Just upload the replacement.  It may or may not overwrite the existing file; we don't care.  Nor do we try to remove the existing file.
        self._deltas.append(DeltaReplace(newfilepath, row=row, serverDirName=serverDirName, NewSourceFilename=newfilepathname, OldFilename=oldSourceFilename))



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