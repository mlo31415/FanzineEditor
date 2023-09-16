from __future__ import annotations

from typing import Union, Optional

import os
import shutil
import wx
import wx.grid
import sys

from GenGUIClass import FanzineGrid
from GenLogDialogClass import LogDialog
from FTP import FTP
from bs4 import BeautifulSoup

from WxDataGrid import DataGrid, Color, GridDataSource, ColDefinitionsList, GridDataRowClass, ColDefinition
from WxHelpers import OnCloseHandling
from LSTFile import *
from HelpersPackage import Bailout,  MessageBox, SetReadOnlyFlag, RemoveTopLevelHTMLTags
from HelpersPackage import  FindLinkInString
from Log import LogOpen, LogClose
from Log import Log as RealLog
from Settings import Settings


def main():

    # Initialize wx
    app=wx.App(False)

    # Set up LogDialog
    global g_LogDialog
    g_LogDialog=LogDialog(None)
    g_LogDialog.Show()

    if sys.gettrace() is None:
        # We are not running under the debugger
        homedir=os.path.split(sys.executable)[0]
    else:
        # We are debugging.
        homedir=os.getcwd()

    LogOpen(os.path.join(homedir, "Log -- FanzineEditor.txt"), os.path.join(homedir, "Log (Errors) -- FanzineEditor.txt"))
    Log(f"Open Logfile {os.path.join(homedir, 'Log -- FanzineEditor.txt')}")
    Log(f"{homedir=}")
    Log(f"{sys.executable=}")

    # Load the global settings dictionary
    Log(f"Settings().Load({os.path.join(homedir, 'FanzineEditor settings.json')})")
    Settings().Load(os.path.join(homedir, "FanzineEditor settings.json"), MustExist=True)
    Log(Settings().Dump())

    # Set the debug/production mode
    global g_debug
    g_debug=Settings().Get("Debug Mode", False)

    if not os.path.exists("FTP Credentials.json"):
        msg=f"Unable to find file 'FTP Credentials.json' file.  Expected to find it in {os.getcwd()}"
        MessageBox(msg, ignoredebugger=True)
        Log(msg)
        exit(0)

    if not FTP().OpenConnection("FTP Credentials.json"):
        MessageBox("Unable to open connection to FTP server fanac.org", ignoredebugger=True)
        Log("Main: OpenConnection('FTP Credentials.json' failed")
        exit(0)

    showLogWindow=Settings().Get("Show log window", False)
    if not showLogWindow:
        g_LogDialog.Destroy()
        g_LogDialog=None

    # Initialize the GUI
    FanzineEditor(None)

    # Run the event loop
    app.MainLoop()

    LogClose()
    sys.exit(1)


#------------------------------------------------------------------------------
g_LogDialog: Optional[LogDialog]=None
def Log(text: str, isError: bool=False, noNewLine: bool=False, Print=True, Clear=False, Flush=False, timestamp=False) -> None:
    RealLog(text, isError=isError, noNewLine=noNewLine, Print=Print, Clear=Clear, Flush=Flush, timestamp=timestamp)
    if g_LogDialog is not None:
        if not text.endswith("\n"):
            text=text+"\n"
        g_LogDialog.textLogWindow.AppendText(text)


# Read the classic fanzine list on fanac.org and return a list of all *fanzine directory names*
def GetFanzineList() -> list[str]:
    html=FTP().GetFileAsString("fanzines", "Classic_Fanzines.html")
    soup=BeautifulSoup(html, 'html.parser')
    table=soup.find_all("table", class_="sortable")[0]
    rows=table.find_all_next("tr")
    row=rows[0]
    rowtable: list[list[str]]=[]
    for row in rows[1:]:
        cols= [str(col) for col in row.children if col != "\n/n"]
        cols=[RemoveTopLevelHTMLTags(col) for col in cols]
        #Log(str(cols))
        rowtable.append(cols)

    # Process the column 1, which is of the form  LINK="Zed-Nielsen_Hayden/ Zed"
    # Split it into Zed-Nielsen_Hayden and Zed, the first being the directoy name and the second being the display name
    namelist: list[str]=[]
    for row in rowtable:
        r1=row[1]
        m=re.match(r'\s*LINK=\"([^/]*)/\s*(.*)\"\s*', r1)
        if m is not None:
            namelist.append(m.groups()[0])
            #Log(str(row))
        else:
            Log(f"GetFanzineList() Failure: {row}")
    return namelist


class FanzineEditor(FanzineGrid):
    def __init__(self, parent):
        FanzineGrid.__init__(self, parent)

        self._dataGrid: DataGrid=DataGrid(self.FanzineGrid)
        self.Datasource=FanzinesPage()      # Note that this is an empty instance

        fanzinesList=GetFanzineList()
        fanzinesList.sort(key=lambda name: name.casefold())
        self.Datasource.FanzineList=fanzinesList

        # Position the window on the screen it was on before
        tlwp=Settings().Get("Top Level Window Position")
        if tlwp:
            self.SetPosition(tlwp)
        tlws=Settings().Get("Top Level Windows Size")
        if tlws:
            self.SetSize(tlws)

        self._signature=0   # We need this member. ClearMainWindow() will initialize it

        #self.ClearMainWindow()
        self.RefreshWindow()

        self.Show(True)


    @property
    def Datasource(self) -> FanzinesPage:       # MainWindow(MainFrame)
        return self._Datasource
    @Datasource.setter
    def Datasource(self, val: FanzinesPage):
        self._Datasource=val
        self._dataGrid.Datasource=val



    def OnExitClicked(self, event):       # MainWindow(MainFrame)
        self.OnClose(event)


    def OnClose(self, event):       # MainWindow(MainFrame)
        if OnCloseHandling(event, self.NeedsSaving(), "The LST file has been updated and not yet saved. Exit anyway?"):
            return
        self.MarkAsSaved()  # The contents have been declared doomed

        # Save the window's position
        pos=self.GetPosition()
        Settings().Put("Top Level Window Position", (pos.x, pos.y))
        size=self.GetSize()
        Settings().Put("Top Level Windows Size", (size.width, size.height))

        self.Destroy()
        LogClose()
        sys.exit(1)



    def CopyTemplateFile(self, settingName: str, newName: str, newDirectory: str, templateDirectory: str) -> bool:
        setupTemplateName=Settings().Get(settingName, default="")
        Log(f"CopyTemplateFile: from '{setupTemplateName}' in '{templateDirectory}' to '{newName}' in '{newDirectory}'")
        if not setupTemplateName:
            MessageBox(f"Settings file does not contain value for key '{settingName}'. Save failed.")
            Log("Settings:")
            Log(Settings().Dump())
            return False

        newpathname=os.path.join(newDirectory, newName)
        # Remove the template if it already exists in the target directory
        if os.path.exists(newpathname):  # Delete any existing file
            Log(f"CopyTemplateFile: '{newpathname}' already exists, so removing it")
            SetReadOnlyFlag(newName, False)
            os.remove(newpathname)

        # Copy the template over, renaming it setup.ftp
        Log(f"CopyTemplateFile: copy '{os.path.join(templateDirectory, setupTemplateName)}'  to  {newpathname}")
        shutil.copy(os.path.join(templateDirectory, setupTemplateName), newpathname)
        return True


    # Save an LST file
    def SaveFile(self, lstfile: LSTFile, name: str):       # MainWindow(MainFrame)
        Log(f"LstFile.SaveFile: save {name}")
        try:
            if not lstfile.Save(name):
                LogError(f"OnSave failed (1) while trying to save {name}")
                MessageBox(f"Failure saving '{name}'")
                return
            self.MarkAsSaved()
        except:
            LogError(f"OnSave failed while trying to save {name}")
            Bailout(PermissionError, "OnSave failed (2) when trying to write file "+name, "LSTError")


    def MaybeSetNeedsSavingFlag(self):       # MainWindow(MainFrame)
        s="Editing "
        if self.NeedsSaving():
            s=s+" *"        # Add on a change marker if needed
        self.SetTitle(s)


    def RefreshWindow(self, DontRefreshGrid: bool=False)-> None:       # MainWindow(MainFrame)
        self.MaybeSetNeedsSavingFlag()
        if not DontRefreshGrid:
            self._dataGrid.RefreshWxGridFromDatasource()


    # ----------------------------------------------
    # Used to determine if anything has been updated
    def Signature(self) -> int:       # MainWindow(MainFrame)
        return self.Datasource.Signature()


    def MarkAsSaved(self):       # MainWindow(MainFrame)
        self._signature=self.Signature()


    def NeedsSaving(self):       # MainWindow(MainFrame)
        return self._signature != self.Signature()


    #------------------
    def OnGridCellChanged(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnGridCellChanged(event)  # Pass event handling to WxDataGrid

        self.RefreshWindow()

    #------------------
    def OnGridCellRightClick(self, event):       # MainWindow(MainFrame)
        # Do generic RMB on grid processing
        self._dataGrid.OnGridCellRightClick(event, self.m_GridPopup)

        # Call the RMB handler
        self.RMBHandler(True, event)

    # ------------------
    def OnGridLabelLeftClick(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnGridLabelLeftClick(event)

    #------------------
    def OnGridLabelRightClick(self, event):       # MainWindow(MainFrame)
        # Do generic RMB on grid processing
        self._dataGrid.OnGridCellRightClick(event, self.m_GridPopup)

        # Call the RMB handler
        self.RMBHandler(False, event)

    # RMB click handling for grid and grid label clicks
    def RMBHandler(self, isCellClick: bool, event):       # MainWindow(MainFrame)
        isLabelClick=not isCellClick

        # Everything remains disabled when we're outside the defined columns
        if self._dataGrid.clickedColumn > self.Datasource.NumCols:    # Click is outside populated columns.  The +1 is because of the split of the 1st column
            return
        if self._dataGrid.clickedRow > self.Datasource.NumRows:      # Click is outside the populated rows
            return

        # ---- Helper fn -----
        def Enable(name: str) -> None:
            mi=self.m_GridPopup.FindItemById(self.m_GridPopup.FindItem(name))
            if mi is not None:
                mi.Enable(True)

        if self._dataGrid.HasSelection():
            Enable("Copy")
            Enable("Erase Selection")
            top, left, bottom, right=self._dataGrid.SelectionBoundingBox()
            if left == right:
                Enable("Sort on Selected Column")
            if bottom-top == 1:
                if self.Datasource.Rows[top][0].lower().endswith(".pdf") and not self.Datasource.Rows[bottom][0].lower().endswith(".pdf") or \
                    not self.Datasource.Rows[top][0].lower().endswith(".pdf") and self.Datasource.Rows[bottom][0].lower().endswith(".pdf"):
                    # Enable Merge if exactly two rows are highlighted and if exactly one of them is a PDF
                    Enable("Merge")

        if self._dataGrid.clipboard is not None:
            Enable("Paste")

        if self._dataGrid.clickedRow != -1:
            Enable("Delete Row(s)")
            Enable("Insert a Row")

        # We enable the Add Column to Left item if we're on a column to the left of the first -- it can be off the right and a column will be added to the right
        if self._dataGrid.clickedColumn > 1:
            Enable("Insert Column to Left")

        # We only allow a column to be deleted if the cursor is in a column with more than one highlighted cell and no hiughlif=ghted cells in other columns.
        if self.Datasource.Element.CanDeleteColumns:
            top, left, bottom, right=self._dataGrid.SelectionBoundingBox()
            if right == left and bottom-top > 0:
                if self._dataGrid.clickedColumn == right:
                    Enable("Delete Column")


        # We enable the Add Column to right item if we're on any existing column
        if self._dataGrid.clickedColumn > 0:        # Can't insert columns between the 1st two
            Enable("Insert Column to Right")

        if self._dataGrid.clickedRow == -1: #Indicates we're on a column header
            Enable("Rename Column")

        if self._dataGrid.clickedRow >= 0 and self._dataGrid.clickedColumn >= 0:
            Enable("Add a Link")

        # Check to see if there is a hyperlink in this row
        if self._dataGrid.clickedRow >= 0:
            row=self.Datasource.Rows[self._dataGrid.clickedRow]
            for col in row:
                _, link, _, _=FindLinkInString(col)
                if link != "":
                    Enable("Clear All Links")
                    break

        # We only enable Extract Scanner when we're in the Notes column and there's something to extract.
        if self.Datasource.ColDefs[self._dataGrid.clickedColumn].Preferred == "Notes":
            # We only want to enable the "Extract Scanner" item if the Notes column contains scanned by information
            for row in self.Datasource.Rows:
                note=row[self._dataGrid.clickedColumn].lower()
                if "scan by" in note or \
                        "scans by" in note or \
                        "scanned by" in note or \
                        "scanning by" in note or \
                        "scanned at" in note:
                    Enable("Extract Scanner")
                    break

        # We only enable Extract Editor when we're in the Notes column and there's something to extract.
        if self.Datasource.ColDefs[self._dataGrid.clickedColumn].Preferred == "Notes":
            # We only want to enable the "Extract Editor" item if the Notes column contains edited by information
            for row in self.Datasource.Rows:
                note=row[self._dataGrid.clickedColumn].lower()
                if "edited by" in note or \
                        "editor " in note:
                    Enable("Extract Editor")
                    break


    # ------------------
    # Initialize the main window to empty
    # This also initiazes the datasource
    def ClearMainWindow(self):       # MainWindow(MainFrame)

        # Re-initialize the form

        # Create an empty datasource
        self.Datasource._fanzineList=[]

        # Update the dialog's grid from the data
        self._dataGrid.RefreshWxGridFromDatasource(RetainSelection=False)

        # Set the signature to the current (empty) state so any change will trigger a request to save on exit
        self.MarkAsSaved()


#=============================================================
# An individual file to be listed under a convention
# This is a single row
class FanzinesPageRow(GridDataRowClass):

    def __init__(self, cells: list[str]):
        GridDataRowClass.__init__(self)
        self._cells: list[str]=cells

    def __str__(self):      # FanzineTableRow(GridDataRowClass)
        return str(self._cells)

    def __len__(self):     # FanzineTableRow(GridDataRowClass)
        return len(self._cells)

    def Extend(self, s: list[str]) -> None:    # FanzineTableRow(GridDataRowClass)
        self._cells.extend(s)

    # Make a deep copy of a FanzineTableRow
    def Copy(self) -> FanzinesPageRow:      # FanzineTableRow(GridDataRowClass)
        ftr=FanzinesPageRow([])
        ftr._cells=self._cells
        return ftr

    # We multiply the cell has by the cell index (+1) so that moves right and left also change the signature
    def Signature(self) -> int:      # FanzineTableRow(GridDataRowClass)
        return sum([(i+1)*hash(x) for i, x in enumerate(self._cells)])

    @property
    def Cells(self) -> list[str]:      # FanzineTableRow(GridDataRowClass)
        return self._cells
    @Cells.setter
    def Cells(self, newcells: list[str]):
        self._cells=newcells

    @property
    def CanDeleteColumns(self) -> bool:      # FanzineTableRow(GridDataRowClass)
        return True

    # This deletes a single column from the datasource.
    # It must be implemented here because WxDataGrid doesn't understand the details of the DataSource
    def DelCol(self, icol: int) -> None:      # FanzineTableRow(GridDataRowClass)
        del self._cells[icol]


    def __getitem__(self, index: Union[int, slice]) -> str | list[str]:      # FanzineTableRow(GridDataRowClass)
        if type(index) is int:
            return self._cells[index]
        if type(index) is slice:
            return self._cells[index]
            #return self._cells(self.List[index])
        raise KeyError

    def __setitem__(self, index: Union[str, int, slice], value: Union[str, int, bool]) -> None:      # FanzineTableRow(GridDataRowClass)
        if type(index) is int:
            self._cells[index]=value
            return
        raise KeyError

    def IsEmptyRow(self) -> bool:      # FanzineTableRow(GridDataRowClass)
        return all([cell == "" for cell in self._cells])


#####################################################################################################
#####################################################################################################

class FanzinesPage(GridDataSource):
    def __init__(self):
        GridDataSource.__init__(self)
        self._numCols=5
        self._colDefs: ColDefinitionsList=ColDefinitionsList([])
        for i in range(self._numCols):
            self._colDefs.append(ColDefinition("", IsEditable="no"))
        self._fanzineList: list[FanzinesPageRow]=[]
        self._gridDataRowClass=FanzinesPageRow



    def Signature(self) -> int:        # FanzineTablePage(GridDataSource)
        return sum([x.Signature()*(i+1) for i, x in enumerate(self._fanzineList)])

    # Inherited from GridDataSource
    @property
    def Rows(self) -> list[FanzinesPageRow]:        # FanzineTablePage(GridDataSource)
        return self._fanzineList
    @Rows.setter
    def Rows(self, rows: list) -> None:        # FanzineTablePage(GridDataSource)
        self._fanzineList=rows

    @property
    def NumRows(self) -> int:        # FanzineTablePage(GridDataSource)
        return len(self._fanzineList)

    def __getitem__(self, index: int) -> FanzinesPageRow:        # FanzineTablePage(GridDataSource)
        return self.Rows[index]

    def __setitem__(self, index: int, val: FanzinesPageRow) -> None:        # FanzineTablePage(GridDataSource)
        self._fanzineList[index]=val


    @property
    def SpecialTextColor(self) -> Optional[Color]:        # FanzineTablePage(GridDataSource)
        return self._specialTextColor
    @SpecialTextColor.setter
    def SpecialTextColor(self, val: Optional[Color]) -> None:        # FanzineTablePage(GridDataSource)
        self._specialTextColor=val

    def CanAddColumns(self) -> bool:        # FanzineTablePage(GridDataSource)
        return False

    def CanMoveColumns(self) -> bool:     # FanzineTablePage(GridDataSource)
        return False             # Override if columns can't be moved


    def InsertEmptyRows(self, insertat: int, num: int=1) -> None:        # FanzineTablePage(GridDataSource)
        for i in range(num):
            ftr=FanzinesPageRow([""]*self.NumCols)
            self._fanzineList.insert(insertat+i, ftr)


if __name__ == "__main__":
    main()