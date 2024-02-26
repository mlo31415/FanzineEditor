from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from FTP import FTP
from HelpersPackage import Int0, RemoveAccents


# An individual file to be listed under a convention
# This is a single row
class PDFFile():
    def __init__(self):
        self._displayTitle: str=""      # The name as shown to the world on the website
        self._notes: str=""             # The free-format description
        self._localfilename: str=""     # The filename of the source file
        self._localpathname: str="."    # The local pathname of the source file (path+filename)
        self._sitefilename: str=""      # The name to be used for this file on the website
        self._size: int=0               # The file's size in bytes
        self._isText: bool=False        # Is this a piece of text rather than a convention?
        self._isLink: bool=False        # Is this a link?

        self._URL: str=""               # The URL to be used for a link. (This is ignored if _isLink == False.)
                                        # It will be displayed using the localfilename as the link text.
                                        # Note that this is different than the URL method in the other frames
        self._pages: int=0    # Page count

    def __str__(self):      # ConFile(GridDataRowClass)
        s=""
        if len(self.SourceFilename) > 0:
            s+="Source="+self.SourceFilename+"; "
        if len(self.SiteFilename) > 0:
            s+="Sitename="+self.SiteFilename+"; "
        if len(self.DisplayTitle) > 0:
            s+="Display="+self.DisplayTitle+"; "
        if len(self.Notes) > 0:
            s+="Notes="+self.Notes+"; "
        if len(self.URL) > 0:
            s+="URL="+self.URL+"; "
        if self.Size > 0:
            s+="Size="+str(self.Size)+"; "
        if self.Pages > 0:
            s+="Pages="+str(self.Pages)+"; "
        if self.IsTextRow:
            s+="IsTextRow; "
        if self.IsLinkRow:
            s+="IsLinkRow; "

        return s

    # Make a deep copy of a ConFile
    def Copy(self) -> PDFFile:      # ConFile(GridDataRowClass)
        cf=PDFFile()
        cf._displayTitle=self._displayTitle
        cf._notes=self._notes
        cf._localfilename=self._localfilename
        cf._localpathname=self._localpathname
        cf._sitefilename=self._sitefilename
        cf._size=self._size
        cf._isText=self._isText
        cf._isLink=self._isLink
        cf._URL=self._URL
        cf._pages=self._pages
        return cf

    def Signature(self) -> int:      # ConFile(GridDataRowClass)
        tot=hash(self._displayTitle.strip()+self._notes.strip()+self._localfilename.strip()+self._localpathname.strip()+self._sitefilename.strip()+self._URL.strip())
        return tot+self._size+hash(self._isText)+self.Pages

    # Serialize and deserialize
    def ToJson(self) -> str:      # ConFile(GridDataRowClass)
        d={"ver": 10,
           "_displayTitle": self._displayTitle,
           "_notes": self._notes,
           "_localpathname": self._localpathname,
           "_filename": self._localfilename,
           "_sitefilename": self._sitefilename,
           "_isText": self._isText,
           "_isLink": self._isLink,
           "_URL": self._URL,
           "_pages": self._pages,
           "_size": self._size}
        return json.dumps(d)

    def FromJson(self, val: str) -> PDFFile:      # ConFile(GridDataRowClass)
        d=json.loads(val)
        self._displayTitle=d["_displayTitle"]
        self._notes=d["_notes"]
        self._localpathname=d["_localpathname"]
        self._localfilename=d["_filename"]
        self._size=d["_size"]
        if d["ver"] > 4:
            self._sitefilename=d["_sitefilename"]
        if d["ver"] <= 4 or self._sitefilename.strip() == "":
            self._sitefilename=self._displayTitle
        if d["ver"] > 5:
            self._isText=d["_isText"]
        if d["ver"] > 6:
            self._pages=d["_pages"]
            if self._pages is None:
                self._pages=0
        if d["ver"] > 7:
            self._isLink=d["_isLink"]
        if d["ver"] > 8:
            self._URL=d["_URL"]
        return self

    @property
    def DisplayTitle(self) -> str:      # ConFile(GridDataRowClass)
        return self._displayTitle
    @DisplayTitle.setter
    def DisplayTitle(self, val: str) -> None:      # ConFile(GridDataRowClass)
        self._displayTitle=val

    @property
    def Notes(self) -> str:      # ConFile(GridDataRowClass)
        return self._notes
    @Notes.setter
    def Notes(self, val: str) -> None:      # ConFile(GridDataRowClass)
        self._notes=val

    @property
    def SourcePathname(self) -> str:      # ConFile(GridDataRowClass)
        return self._localpathname
    @SourcePathname.setter
    def SourcePathname(self, val: str) -> None:      # ConFile(GridDataRowClass)
        self._localpathname=val
        self._localfilename=os.path.basename(val)


    @property
    def SourceFilename(self) -> str:      # ConFile(GridDataRowClass)
        return self._localfilename
    @SourceFilename.setter
    def SourceFilename(self, val: str) -> None:      # ConFile(GridDataRowClass)
        self._localfilename=val
        self._localpathname="invalidated"

    @property
    def SiteFilename(self) -> str:      # ConFile(GridDataRowClass)
        return self._sitefilename
    @SiteFilename.setter
    def SiteFilename(self, val: str) -> None:      # ConFile(GridDataRowClass)
        self._sitefilename=RemoveAccents(val)


    @property
    def Size(self) -> int:      # ConFile(GridDataRowClass)
        return self._size
    @Size.setter
    def Size(self, val: int) -> None:      # ConFile(GridDataRowClass)
        self._size=val

    @property
    def Pages(self) -> int:      # ConFile(GridDataRowClass)
        if self._pages is None:
            return 0
        return self._pages
    @Pages.setter
    def Pages(self, val: int|str) -> None:      # ConFile(GridDataRowClass)
        if type(val) is str:
            val=Int0(val)
        self._pages=val

    @property
    def IsTextRow(self) -> bool:      # ConFile(GridDataRowClass)
        return self._isText
    @IsTextRow.setter
    def IsTextRow(self, val: bool) -> None:
        self._isText=val

    @property
    def IsLinkRow(self) -> bool:      # ConFile(GridDataRowClass)
        return self._isLink
    @IsLinkRow.setter
    def IsLinkRow(self, val: bool) -> None:
        self._isLink=val

    @property
    def URL(self) -> str:      # ConFile(GridDataRowClass)
        if not self.IsLinkRow:
            return ""
        # The URL is always stored in column 0: Source Files name
        return self._localfilename

    @URL.setter
    def URL(self, val: str) -> None:      # ConFile(GridDataRowClass)
        self._URL=val

    # Get or set a value by name or column number in the grid
    #def GetVal(self, name: Union[str, int]) -> Union[str, int]:
    def __getitem__(self, index: int|slice) -> str|int:      # ConFile(GridDataRowClass)
        # (Could use return eval("self."+name))
        if index == 0:
            return self.SourceFilename
        if index == 1:
            return self.SiteFilename
        if index == 2:
            return self.DisplayTitle
        if index == 3:
            if self.Pages == 0:
                return ""
            return self.Pages
        if index == 4:
            return self.Notes
        return "Val can't interpret '"+str(index)+"'"

    #def SetVal(self, nameOrCol: Union[str, int], val: Union[str, int]) -> None:
    def __setitem__(self, index: int|slice, value: str) -> None:      # ConFile(GridDataRowClass)
        # (Could use return eval("self."+name))
        if index == 0:
            self.SourceFilename=value
            return
        if index == 1:
            self.SiteFilename=value
            return
        if index == 2:
            self.DisplayTitle=value
            return
        if index == 3:
            if isinstance(value, int):
                self.Pages=value
            else:
                self.Pages=Int0(value.strip())
            return
        if index == 4:
            self.Notes=value
            return
        print("SetVal can't interpret '"+str(index)+"'")
        raise KeyError

    def IsEmptyRow(self) -> bool:      # ConFile(GridDataRowClass)
        return self.SourceFilename != "" or self.SiteFilename != "" or self.DisplayTitle != "" or self.Pages != 0 or self.Notes != ""



# These classes track changes to the list of files for a particular Con Instance
# All it cares about is the files and their names
# Once the user is done editing the ConInstance page and does an upload, this class will provide the instructions
#   for the upload so that all the accumulated edits get up there.

@dataclass
class Delta:
    Verb: str+""
    Con: PDFFile
    Oldname: str=""

    def __str__(self) -> str:
        s=self.Verb+": "+str(self.Con)
        if self.Oldname is not None and len(self.Oldname) > 0:
            s+=" oldname="+self.Oldname
        return s


# Changes (the tuple providing info needed to defined them) are (in the order in which they must be executed):
#       Delete a file which exists on the website ("delete", con, "")
#       Rename an existing website file ("rename", con, oldname)
#       Add a new file ("add", con, "")
#       Replace an existing file ("replace", con, oldname)
# When two deltas affect the same file, they are usually merged.  (E.g., Add followed by Delete cancels out; Add followed by Rename updates the Add with the new name.)
class ConInstanceDeltaTracker:
    def __init__(self):
        self._deltas: list[Delta]=list()

    def __str__(self) -> str:
        if self._deltas is None or len(self._deltas) == 0:
            return ""
        s=""
        for d in self._deltas:
            s+=">>"+str(d)+"\n"
        return s

    def Add(self, con: PDFFile) -> None:
        self._deltas.append(Delta("add", con, ""))

    def Delete(self, con: PDFFile) -> None:
        # If the item being deleted was just added, simply remove the add from the deltas list
        for i, item in enumerate(self._deltas):
            if item.Verb == "add":
                if item.Con.DisplayTitle == con.DisplayTitle:
                    del self._deltas[i]
                    return
        # OK, the item is not queued to be added so it must already be on the website: add a delete action to the deltas list
        self._deltas.append(Delta("delete", con, ""))

    # Change the name of a file on the website site
    def Rename(self, con: PDFFile, oldname: str) -> None:
        # First check to see if this is a rename of a rename.  If it is, merge them by updating the existing rename.
        for i, item in enumerate(self._deltas):
            if item.Verb == "rename":
                if item.Oldname == con.DisplayTitle:
                    self._deltas[i]=Delta("rename", con, oldname)
                    return
            # Now check to see if this is a rename of a newly-added file.  If so, we just modify the add Delta
            elif item.Verb == "add":
                if item.Con.DisplayTitle == con.DisplayTitle:
                    item.Con=con
                    return

        # If it doesn't match anything in the delta list, then it must be a rename of an existing file.
        self._deltas.append(Delta("rename", con, oldname))

    # We want to replace one file with another
    def Replace(self, con: PDFFile, oldname: str):
        # Check to see if the replacement is in a row yet to be uploaded or a row which has been renamed.
        for i, item in enumerate(self._deltas):
            if item.Verb == "rename":
                if item.Con.SourcePathname == con.SourcePathname:
                    self._deltas[i]=Delta("rename", con, oldname)
                    return
            # Now check to see if this is a rename of a newly-added file
            elif item.Verb == "add":
                if item.Con.SourcePathname == con.SourcePathname:
                    # Just update the local pathname in the add entry
                    self._deltas[i].Con.SourcePathname=con.SourcePathname
                    return

        # If it doesn't match anything in the delta list, then it must be a new local file to replace an old one in an existing entry
        # We need to delete the old file and then upload the new.
        self._deltas.append(Delta("replace", con, oldname))


    @property
    def Num(self) -> int:
        return len(self._deltas)

    @property
    def Deltas(self) -> list[Delta]:
        return self._deltas


class UpdateFTPLog:
    g_ID: str|None=None

    def Init(self, id: str):
        UpdateFTPLog.g_ID=id
        pass

    def Log(self, series: str, con: str = "", deltas: ConInstanceDeltaTracker|None = None):
        lines="Uploaded ConInstance: "+series+":"+con+"   "+"["+UpdateFTPLog.g_ID+"  "+datetime.now().strftime("%A %B %d, %Y  %I:%M:%S %p")+" EST]\n"
        if deltas is not None and deltas.Num > 0:
            lines+="^^deltas by "+FTP().GetEditor()+":\n"+str(deltas)+"\n"
        FTP().AppendString("/updatelog.txt", lines)
        pass

    def LogText(self, txt: str):
        FTP().AppendString("/updatelog.txt", txt+"   ["+UpdateFTPLog.g_ID+"  "+FTP().GetEditor()+"  "+datetime.now().strftime("%A %B %d, %Y  %I:%M:%S %p")+" EST]\n")