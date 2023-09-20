from __future__ import annotations

from typing import Union, Optional

import os
import wx
import wx.grid
import sys


from FTP import FTP
from bs4 import BeautifulSoup

from WxDataGrid import DataGrid, GridDataSource, ColDefinitionsList, GridDataRowClass, ColDefinition
from WxHelpers import OnCloseHandling
from LSTFile import *
from HelpersPackage import MessageBox, RemoveTopLevelHTMLTags
from Log import LogOpen, LogClose
from Log import Log as RealLog
from Settings import Settings

from FanzineIndexPageEdit import FanzineIndexPageWindow
from GenGUIClass import FanzinesGrid
from GenLogDialogClass import LogDialog


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


class FanzineEditor(FanzinesGrid):
    def __init__(self, parent):
        FanzinesGrid.__init__(self, parent)

        self._dataGrid: DataGrid=DataGrid(self.wxGrid)
        self.Datasource=FanzinesPage()      # Note that this is an empty instance

        self._fanzinesList=GetFanzineList()
        self._fanzinesList.sort(key=lambda name: name.casefold())
        self.Datasource.FanzineList=self._fanzinesList

        self._dataGrid.HideRowLabels()
        self._dataGrid.HideColLabels()

        # Position the window on the screen it was on before
        tlwp=Settings().Get("Top Level Window Position")
        if tlwp:
            self.SetPosition(tlwp)
        tlws=Settings().Get("Top Level Windows Size")
        if tlws:
            self.SetSize(tlws)

        self._signature=0   # We need this member. ClearMainWindow() will initialize it

        #self.ClearMainWindow()
        self.MarkAsSaved()
        self.RefreshWindow()

        self.Show(True)


    @property
    def Datasource(self) -> FanzinesPage:       # FanzineEditor(FanzineGrid)
        return self._Datasource
    @Datasource.setter
    def Datasource(self, val: FanzinesPage):
        self._Datasource=val
        self._dataGrid.Datasource=val


    def OnClose(self, event):       # FanzineEditor(FanzineGrid)
        if OnCloseHandling(event, self.NeedsSaving(), "The list of fanzines has been updated and not yet saved. Exit anyway?"):
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


    def UpdateNeedsSavingFlag(self):       # FanzineEditor(FanzineGrid)
        s="Editing "
        if self.NeedsSaving():
            s=s+" *"        # Add on a change marker if needed
        self.SetTitle(s)


    def RefreshWindow(self, DontRefreshGrid: bool=False)-> None:       # FanzineEditor(FanzineGrid)
        self.UpdateNeedsSavingFlag()
        if not DontRefreshGrid:
            self._dataGrid.RefreshWxGridFromDatasource()


    # ----------------------------------------------
    # Used to determine if anything has been updated
    def Signature(self) -> int:       # FanzineEditor(FanzineGrid)
        return self.Datasource.Signature()


    def MarkAsSaved(self):       # FanzineEditor(FanzineGrid)
        self._signature=self.Signature()


    def NeedsSaving(self):       # FanzineEditor(FanzineGrid)
        return self._signature != self.Signature()


    def OnSearchText(self, event):
        searchtext=self.tSearch.GetValue()
        if searchtext != "":
            fanzinelist=[x for x in self._fanzinesList if searchtext.casefold() in x.casefold().replace("_", " ")]
            self.Datasource.FanzineList=fanzinelist
            self.RefreshWindow()


    def OnClearSearch( self, event ):
        self.Datasource.FanzineList=self._fanzinesList
        self.tSearch.SetValue("")
        self.RefreshWindow()


    #-------------------
    def OnGridCellDoubleClick(self, event):        # DataGrid
        #self.SaveClickLocation(vent)
        url=self._Datasource.Rows[event.Row][event.Col]
        fsw=FanzineIndexPageWindow(None, url)
        if fsw.failure:
            Log(f"FanzineIndexPageWindow('{url}') failed")


    # ------------------
    # Initialize the main window to empty
    # This also initiazes the datasource
    def ClearMainWindow(self):       # FanzineEditor(FanzineGrid)

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
        return False

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
        self._rows: list[FanzinesPageRow]=[]
        self._gridDataRowClass=FanzinesPageRow

        self._fanzineList:list[str]=[]



    def Signature(self) -> int:        # FanzinesPage(GridDataSource)
        return sum([x.__hash__() *(i+1) for i, x in enumerate(self._fanzineList)])


    # Inherited from GridDataSource
    @property
    def Rows(self) -> list[FanzinesPageRow]:        # FanzinesPage(GridDataSource)
        return self._rows
    @Rows.setter
    def Rows(self, rows: list) -> None:        # FanzinesPage(GridDataSource)
        self._rows=rows

    @property
    def NumRows(self) -> int:        # FanzinesPage(GridDataSource)
        numcells=len(self._fanzineList)
        if numcells%self._numCols == 0:
            return numcells//self._numCols
        return numcells//self._numCols+1

    @property
    def FanzineList(self) -> list[str]:
        return self._fanzineList
    @FanzineList.setter
    def FanzineList(self, val: list[str]):
        self._fanzineList=val
        numrows=len(val)/self._numCols
        if len(val)%self._numCols != 0:
            numrows+=1
        self._rows=[]
        row=self._rows
        for i in range(len(val)):
            row=i//self._numCols
            col=i%self._numCols
            if col == 0:
                self._rows.append(self._gridDataRowClass(self._numCols*[""]))
            self._rows[row][col]=val[i]



    def __getitem__(self, index: int) -> FanzinesPageRow:        # FanzinesPage(GridDataSource)
        return self.Rows[index]

    def __setitem__(self, index: int, val: FanzinesPageRow) -> None:        # FanzinesPage(GridDataSource)
        self._fanzineList[index]=val

    def CanAddColumns(self) -> bool:        # FanzinesPage(GridDataSource)
        return False

    def CanMoveColumns(self) -> bool:     # FanzinesPage(GridDataSource)
        return False             # Override if columns can't be moved


    def InsertEmptyRows(self, insertat: int, num: int=1) -> None:        # FanzinesPage(GridDataSource)
        for i in range(num):
            ftr=FanzinesPageRow([""]*self.NumCols)
            self._fanzineList.insert(insertat+i, ftr)


if __name__ == "__main__":
    main()