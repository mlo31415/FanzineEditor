import os
import ctypes

from GenGUIClass import NewFanzineDialogGen
from HelpersPackage import FanzineNameToDirName
from WxHelpers import AddChar

class NewFanzineWindow(NewFanzineDialogGen):

    def __init__(self, parent, rootDirectory: str):
        self._directory: str=""
        self._fanzineName=""
        self._output: str=""
        self._rootDirectory: str=rootDirectory
        NewFanzineDialogGen.__init__(self, parent)

    @property
    def Directory(self) -> str:
        return self._directory
    @Directory.setter
    def Directory(self, s: str):
        self._directory=s

    @property
    def FanzineName(self) -> str:
        return self._fanzineName
    @FanzineName.setter
    def FanzineName(self, s: str):
        self._fanzineName=s

    def OnCharFanzine( self, event ):
        # The only time we update the local directory
        fname=AddChar(self.tFanzineName.GetValue(), event.GetKeyCode())
        self.tFanzineName.SetValue(fname)
        self.tDirName.SetValue(FanzineNameToDirName(self.tFanzineName.GetValue()).upper())
        self.tFanzineName.SetInsertionPoint(999)    # Make sure the cursor stays at the end of the string

    def OnTextFanzine( self, event ):
        self.tDirName.SetValue(FanzineNameToDirName(self.tFanzineName.GetValue()))


    def OnCreate(self, event):
        self._directory=self.tDirName.GetValue()
        self._fanzineName=self.tFanzineName.GetValue()

        if self._fanzineName == "":
            ctypes.windll.user32.MessageBoxW(0, "You must supply a fanzine name", "Trouble", 0)
            return

        if self._directory == "":
            ctypes.windll.user32.MessageBoxW(0, "You must supply a directory name", "Trouble", 0)
            return

        if os.path.exists(os.path.join(self._rootDirectory, self._directory)):
            msg=f"Name unavailable\nA directory named {self._directory} already exists in root directory\n"
            ctypes.windll.user32.MessageBoxW(0, msg, "Trouble", 0)
            return


        self.Destroy()

    def OnCancel(self, event):
        self.Destroy()

