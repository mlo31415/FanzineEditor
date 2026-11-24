from __future__ import annotations

from FTP import FTP
from Log import Log, LogError


#==========================================================================================================
# The master list of tags which a fanzine index page may carry. It's kept on the server at the fanzines root (next to
# Classic_Fanzines.html) in "Master Tags List.txt" as a comma-separated list (a tag can't contain a comma).
# It's read when FE starts. During a session, tags can be added to it (never removed: that's done by editing the file
# by hand), and it's uploaded along with the list of fanzines.
# Use it as MasterTags(): every instance shares the one list.
class MasterTags:
    Filename="Master Tags List.txt"
    _tags: list[str]=[]
    _edited: bool=False

    # Read the list from the server's root directory (e.g. "/fanzines"), creating an empty one if there is none.
    # Return False if it could be neither read nor created.
    def Load(self, rootDir: str) -> bool:
        MasterTags._edited=False
        if not FTP().FileExists(f"{rootDir}/{MasterTags.Filename}"):
            Log(f"MasterTags.Load(): there is no {rootDir}/{MasterTags.Filename}, so an empty one is being created")
            MasterTags._tags=[]
            if not FTP().PutFileAsString(rootDir, MasterTags.Filename, ""):
                LogError(f"MasterTags.Load(): could not create {rootDir}/{MasterTags.Filename} because: {FTP().LastMessage}")
                return False
            return True

        s=FTP().GetFileAsString(rootDir, MasterTags.Filename)
        if s is None:
            LogError(f"MasterTags.Load(): could not read {rootDir}/{MasterTags.Filename} because: {FTP().LastMessage}")
            return False
        MasterTags._tags=[]
        for tag in SplitTags(s):
            if not self.Contains(tag):
                MasterTags._tags.append(tag)
        MasterTags._tags.sort(key=lambda x: x.casefold())
        Log(f"MasterTags.Load(): {len(MasterTags._tags)} tags read")
        return True


    # Upload the list to the server's root directory. Return False if that failed.
    def Upload(self, rootDir: str) -> bool:
        if not FTP().PutFileAsString(rootDir, MasterTags.Filename, ", ".join(MasterTags._tags)):
            LogError(f"MasterTags.Upload(): could not upload {rootDir}/{MasterTags.Filename} because: {FTP().LastMessage}")
            return False
        MasterTags._edited=False
        return True


    # The tags, in alphabetical order
    @property
    def Tags(self) -> list[str]:
        return list(MasterTags._tags)

    # Has a tag been added since the list was read or uploaded?
    @property
    def Edited(self) -> bool:
        return MasterTags._edited
    @Edited.setter
    def Edited(self, val: bool) -> None:
        MasterTags._edited=val

    # Tags are matched ignoring case and surrounding spaces. Return the master list's spelling of a tag, or None.
    def Find(self, tag: str) -> str|None:
        for x in MasterTags._tags:
            if x.casefold() == tag.strip().casefold():
                return x
        return None

    def Contains(self, tag: str) -> bool:
        return self.Find(tag) is not None

    def Add(self, tag: str) -> None:
        tag=tag.strip()
        if tag == "" or "," in tag or self.Contains(tag):
            return
        MasterTags._tags.append(tag)
        MasterTags._tags.sort(key=lambda x: x.casefold())
        MasterTags._edited=True


# Turn a comma-separated list of tags into a list, dropping blanks
def SplitTags(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip() != ""]
