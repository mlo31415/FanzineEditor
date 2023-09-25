from __future__ import annotations

from typing import Optional

import os
import wx
import wx.grid
import sys
import re


from FTP import FTP
from bs4 import BeautifulSoup

from WxDataGrid import DataGrid, GridDataSource, ColDefinitionsList, GridDataRowClass, ColDefinition
from WxHelpers import OnCloseHandling, ProgressMsg
from HelpersPackage import MessageBox, RemoveTopLevelHTMLTags, SearchExtractAndRemoveBoundedAll
from Log import LogOpen, LogClose, LogError
from Log import Log as RealLog
from Settings import Settings

from FanzineIndexPageEdit import FanzineIndexPageWindow
from GenGUIClass import FanzinesGrid
from GenLogDialogClass import LogDialog
from ClassicTableEntry import ClassicTableEntryDlg
from ClassicFanzinesLine import ClassicFanzinesLine


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


#==========================================================================================================
# Read the classic fanzine list on fanac.org and return a list of all *fanzine directory names*
def GetFanzineList() -> list[ClassicFanzinesLine] | None:
    html=FTP().GetFileAsString("Fanzines-test", "Classic_Fanzines.html")
    if html is None:
        LogError(f"Unable to download '/Fanzines-test/Classic_Fanzines.html'")
        return None

    soup=BeautifulSoup(html, 'html.parser')
    table=soup.find_all("table", class_="sortable")[0]
    rows=table.find_all_next("tr")
    row=rows[0]
    rowtable: list[list[str]]=[]
    for row in rows[1:]:
        srow=str(row)
        if "<form action=" in srow[:30]:  # I don't know where this line is coming from (it shows up as the last row, but does not appear on the website!)>
            continue

        # Parse into rows by breaking on {tr}...</tr>
        cols, srow=SearchExtractAndRemoveBoundedAll(srow, r"(<td)(.*?)<\/td>")

        #Log(str(cols))
        rowtable.append(cols)

    # Process each of the columns
    namelist: list[ClassicFanzinesLine]=[]
    for row in rowtable:
        if "<form action=" in row[0]:    # I don't know where this is coming from (this shows up as the last row, but does not appear on the website)>
            continue

        cfl=ClassicFanzinesLine()
        # Cell 0
        # This is the blue dot.  No information here, it seems.
        str(row[0])
        # Cell 1
        # <td sorttable_customkey="1940S ONE SHOTS"><a href="1940s_One_Shots/"><strong>1940s One Shots</strong></a></td>
        # This cell is of one of two possible formats:
        # (1) '<a href="Zed-Nielsen_Hayden/"><strong>Zed</strong></a>'
        # This is the typical case with URL and text
        # (2) '<a href="Zed/"><strong>Zed, The </strong></a><br/> Die Zeitschrift Fur Vollstandigen Unsinn'
        # In aa few cases, the fanzine has a list of alternative names following.
        m=re.search(r'<a href=[\'\"]?([^>]+?)/?[\'\"]?>(.+)</a>(.*)$', row[1].strip(), flags=re.IGNORECASE)
        if m is None:
            Log(f"GetFanzineList() Failure: {row}")
            continue

        cfl._url=m.groups()[0]
        cfl._displayName=m.groups()[1]
        cfl._otherNames=m.groups()[2]
        #TODO still need to get sort key

        # Cell 2: type
        # '<td sorttable_customkey="SPEER, JACK">Jack Speer'
        str(row[2])

        # Cell 3
        # '<td sorttable_customkey="19390000">1939-1943'
        str(row[3])

        # Cell 4
        # '<td>Fanzine'

        # Cell 5
        # '<td class="right" sorttable_customkey="00001">1 '

        #Cell 6
        # '<td sorttable_customkey="zzzz"><br/>'

        namelist.append(cfl)
        #Log(str(row))

    return namelist


#==========================================================================================================
class FanzineEditor(FanzinesGrid):
    def __init__(self, parent):
        FanzinesGrid.__init__(self, parent)

        self._dataGrid: DataGrid=DataGrid(self.wxGrid)
        self.Datasource=FanzinesPage()      # Note that this is an empty instance

        with ProgressMsg(None, "Downloading main fanzine page"):
            val=GetFanzineList()
            if val is None or len(val) == 0:
                return
            self._fanzinesList: list[ClassicFanzinesLine]=val
            self._fanzinesList.sort(key=lambda cfl: cfl.URL)
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


    def OnSearchText(self, event):       # FanzineEditor(FanzineGrid)
        searchtext=self.tSearch.GetValue()
        if searchtext != "":
            fanzinelist=[x for x in self._fanzinesList if searchtext.casefold() in x.casefold().replace("_", " ")]
            self.Datasource.FanzineList=fanzinelist
            self.RefreshWindow()


    def OnClearSearch( self, event ):       # FanzineEditor(FanzineGrid)
        self.Datasource.FanzineList=self._fanzinesList
        self.tSearch.SetValue("")
        self.RefreshWindow()


    #-------------------
    def OnGridCellDoubleClick(self, event):       # FanzineEditor(FanzineGrid)
        #self.SaveClickLocation(vent)
        url=self._Datasource.Rows[event.Row][event.Col]
        fsw=FanzineIndexPageWindow(None, url)
        if fsw.failure:
            MessageBox(f"Unable to load {url}", Title="Loading Fanzine Index page", ignoredebugger=True)
            Log(f"FanzineIndexPageWindow('{url}') failed")


    #-------------------
    def OnGridCellRightClick( self, event ):       # FanzineEditor(FanzineGrid)
        ClassicTableEntryDlg(self.Parent, self._fanzinesList[self.Datasource.NumCols+(event.Row-1)+event.Col-1])


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


    def __getitem__(self, index: int | slice) -> str | list[str]:      # FanzineTableRow(GridDataRowClass)
        if type(index) is int:
            return self._cells[index]
        if type(index) is slice:
            return self._cells[index]
            #return self._cells(self.List[index])
        raise KeyError

    def __setitem__(self, index: str | int | slice, value: str | int | bool) -> None:      # FanzineTableRow(GridDataRowClass)
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
    def FanzineList(self, val: list[ClassicFanzinesLine]):
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
            self._rows[row][col]=val[i].URL



    def __getitem__(self, index: int) -> FanzinesPageRow:        # FanzinesPage(GridDataSource)
        return self.Rows[index]

    def __setitem__(self, index: int, val: str) -> None:        # FanzinesPage(GridDataSource)
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