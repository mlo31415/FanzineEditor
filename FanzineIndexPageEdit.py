from __future__ import annotations

import os
import wx
import wx.grid
import re
import shutil
from datetime import datetime
from math import floor, ceil
from tempfile import gettempdir

from bs4 import BeautifulSoup
import bs4
from pypdf import PdfWriter
import pyperclip

from FTPLog import FTPLog
from GenGUIClass import FanzineIndexPageEditGen
from ClassicFanzinesLine import ClassicFanzinesLine, ClassicFanzinesDate
from DeltaTracker import DeltaTracker
from FanzineNames import FanzineNames
from FanzineDateTime import FanzineDate, InterpretRelativeWords
from FanzineIndexPageTableRow import FanzineIndexPageTableRow

from FTP import FTP

from WxDataGrid import DataGrid, Color, GridDataSource, ColDefinition, ColDefinitionsList, GridDataRowClass, IsEditable
from WxHelpers import OnCloseHandling, ProcessChar
from WxHelpers import ModalDialogManager, ProgressMessage2
from HelpersPackage import IsInt, Int0, Int, ZeroIfNone, RemoveTopLevelHTMLTags, RegularizeBRTags, Pluralize, CanonicizeColumnHeaders
from HelpersPackage import  FindLinkInString, FindIndexOfStringInList, FindIndexOfStringInList2, FindAndReplaceSingleBracketedText, FindAndReplaceBracketedText
from HelpersPackage import InsertBetweenHTMLComments, RemoveHyperlinkContainingPattern, CanonicizeColumnHeaders, RemoveArticles
from HelpersPackage import MakeFancyLink, RemoveFancyLink, WikiUrlnameToWikiPagename, SplitOnSpansOfLineBreaks
from HelpersPackage import SearchAndReplace, RemoveAllHTMLLikeTags, TurnPythonListIntoWordList, StripSpecificTag, RemoveHyperlink
from HelpersPackage import InsertHTMLUsingFanacStartEndCommentPair, ExtractHTMLUsingFanacStartEndCommentPair, SplitListOfNamesOnPattern
from HelpersPackage import  ExtractInvisibleTextInsideFanacComment, TimestampFilename, InsertInvisibleTextInsideFanacComment, ExtractHTMLUsingFanacTagCommentPair
from PDFHelpers import GetPdfPageCount
from HtmlHelpersPackage import HtmlEscapesToUnicode, UnicodeToHtmlEscapes, ConvertHTMLEscapes
from Log import Log, LogError
from Settings import Settings
from FanzineDateTime import MonthNameToInt

# Create default column headers
gStdColHeaders: ColDefinitionsList=ColDefinitionsList([
    ColDefinition("Filename", Type="str", IsEditable=IsEditable.Maybe),
    ColDefinition("Display Text", Type="str"),
    ColDefinition("Link", Type="url"),
    ColDefinition("Text", Type="required str"),
    ColDefinition("Title", Type="str", Preferred="Display Text"),
    ColDefinition("Whole", Type="int", Width=75),
    ColDefinition("WholeNum", Type="int", Width=75, Preferred="Whole"),
    ColDefinition("Vol", Type="int", Width=50),
    ColDefinition("Volume", Type="int", Width=50, Preferred="Vol"),
    ColDefinition("Num", Type="int", Width=50),
    ColDefinition("Number", Type="int", Width=50, Preferred="Num"),
    ColDefinition("Month", Type="month", Width=75),
    ColDefinition("Day", Type="day", Width=50),
    ColDefinition("Year", Type="year", Width=50),
    ColDefinition("Pages", Type="int", Width=50),
    ColDefinition("PDF", Type="str", Width=50),
    ColDefinition("Notes", Type="str", Width=120),
    ColDefinition("Scanned", Type="str", Width=100),
    ColDefinition("Scan", Type="str", Width=100, Preferred="Scanned"),
    ColDefinition("Scanned By", Type="str", Width=100, Preferred="Scanned"),
    ColDefinition("Country", Type="str", Width=50),
    ColDefinition("Editor", Type="str", Width=75),
    ColDefinition("Author", Type="str", Width=75),
    ColDefinition("Mailing", Type="str", Width=75),
    ColDefinition("Repro", Type="str", Width=75)
])


def Tagit(tag: str, contents: str) -> str:
    contents=contents.strip()
    if contents == "":
        return ""
    return f"<{tag}>{contents}</{tag}>"

def ColSelect(row: FanzineIndexPageTableRow, coldefs: ColDefinitionsList, colname: str) -> str:
    if colname in coldefs:
        return row.Cells[coldefs.index(colname)]

    colname=CanonicizeColumnHeaders(colname)
    if colname in coldefs:
        return row.Cells[coldefs.index(colname)]

    for coldef in coldefs:
        if CanonicizeColumnHeaders(coldef.Name).lower() == colname.lower():
            return row.Cells[coldefs.index(colname)]

    return ""


def Editors(row: FanzineIndexPageTableRow, coldefs: ColDefinitionsList, editor: str) -> str:
    issueed=ColSelect(row, coldefs, "editor")
    if len(issueed) > 0:
        return issueed
    return editor

# Format a Month+Day+Year set of columns into a useable date
def DateFmt(row: FanzineIndexPageTableRow, coldefs: ColDefinitionsList) -> str:
    s=ColSelect(row, coldefs, "month")
    if len(s) > 0:
        d=ColSelect(row, coldefs, "day")
        if len(d) > 0:
            s+=", "+d
    y=ColSelect(row, coldefs, "year")
    if len(s) > 0 and s[-1] != " ":
        s+=" "
    s+=y
    return s

def IssueNumber(row: FanzineIndexPageTableRow, coldefs: ColDefinitionsList) -> str:
    issue=ColSelect(row, coldefs, "whole")
    if len(issue) > 0:
        return issue
    vol=ColSelect(row, coldefs, "vol")
    num=ColSelect(row, coldefs, "num")
    s=num
    if len(vol) > 0:
        s=vol+"."+s

    return s



def SpecialNameFormatToHtmlFancylink(val: str|None) ->str|None:
    if val is None:
        return None

    # "Uncredited" is not linked
    if "uncredited" in val.lower() or "various" in val.lower():
        return val

    # If "|" present, input format is <fancyName|displayName>
    if "|" in val:
        fancyName, displayName = val.split("|", 1)
        return MakeFancyLink(fancyName, displayName)

    return MakeFancyLink(val)


def HtmlFancylinkToSpecialNameFormat(val: str) -> str:
    return WikiUrlnameToWikiPagename(val)


class FanzineIndexPageWindow(FanzineIndexPageEditGen):
    def __init__(self, parent, serverDir: str= "", ExistingFanzinesServerDirs: list[str]|None=None):
        FanzineIndexPageEditGen.__init__(self, parent)

        self.failure=True

        self._existingFanzinesServerDirs=ExistingFanzinesServerDirs

        # IsNewDirectory True means this FIP is newly created and has not yet been uploaded.
        # We can tell because an existing fanzine must be opened by supplying a server directory, while for a new fanzine, the server directory must be the empty string
        # Some fields are editable only for new fanzines (which will be in new server directories, allowing some things to be set for the first time.).
        serverDir=serverDir.strip()
        self.IsNewDirectory=serverDir == ""
        self.tServerDirectory.SetValue(serverDir)

        # Figure out the root directory which depends on whether we are in test mode or not
        self.RootDir="fanzines"
        if Settings().IsTrue("Test mode"):
            self.RootDir=Settings().Get("Test Root Directory", self.RootDir)

        # Add a visble flag if we're in test mode
        self.m_TestMode.SetLabelText("")
        if Settings().IsTrue("Test mode"):
            self.m_TestMode.SetLabelText(f"Test Mode: {self.RootDir}")

        # A list of changes to the file stored on the website which will need to be made upon upload.
        self.deltaTracker=DeltaTracker()

        self._AllowFanzineNameEdit=False
        self._allowManualEditOfServerDirectoryName=self.IsNewDirectory        # Is the user allowed to edit the fanzine name? On pressing the edit button, can be true even when not a new fanzine.
        self._manualEditOfServerDirectoryNameBegun=False
        self._allowManualEntryOfLocalDirectoryName=self.IsNewDirectory
        self._manualEditOfLocalDirectoryNameBegun=False
        self._uploaded=False

        # Used to communicate with the fanzine list editor.  It is set to None, but is filled in with a CFL when something is uploaded.
        self.CFL: ClassicFanzinesLine|None=None

        self._dataGrid: DataGrid=DataGrid(self.wxGrid, ColorSingleCellByValue=self.ColorSingleCellByValueOverride)
        self.Datasource=FanzineIndexPage()

        # Get the default PDF directory
        self.PDFSourcePath=Settings().Get("PDF Source Path", os.getcwd())
        #self.LocalDirectoryRoot=Settings().Get("Local Directory Root", ".")

        # Position the window on the screen it was on before
        tlwp=Settings("FanzinesEditor positions.json").Get("Index Page Window Position")
        if tlwp:
            self.SetPosition(tlwp)
        tlws=Settings("FanzinesEditor positions.json").Get("Index Page Window Size")
        if tlws:
            self.SetSize(tlws)

        self._signature=0   # We need this member. ClearMainWindow() will initialize it

        if self.IsNewDirectory:
            # New directory: Do basic setup.
            # Create default column headers
            self._Datasource.ColDefs=ColDefinitionsList([
                gStdColHeaders["Filename"],
                gStdColHeaders["Display Text"],
                gStdColHeaders["Whole"],
                gStdColHeaders["Vol"],
                gStdColHeaders["Number"],
                gStdColHeaders["Month"],
                gStdColHeaders["Day"],
                gStdColHeaders["Year"],
                gStdColHeaders["Pages"],
                gStdColHeaders["Notes"]
            ])

        else:
            # This is an existing directory
            # Load the fanzine index page
            with ModalDialogManager(ProgressMessage2,f"Downloading Fanzine Index Page: '{serverDir}'", parent=parent):
                self.failure=False
                if not self.Datasource.GetFanzineIndexPage(serverDir):
                    self.failure=True
                    return

            # Now load the fanzine issue data
            #self._dataGrid.HideRowLabels()
            self._dataGrid._grid.SetRowLabelSize(40)

            self._dataGrid.NumCols=self.Datasource.NumCols
            if self._dataGrid.NumRows > self.Datasource.NumRows:
                self._dataGrid.DeleteRows(self.Datasource.NumRows, self._dataGrid.NumRows-self.Datasource.NumRows)
            else:
                self._dataGrid.AppendRows(self.Datasource.NumRows)

            # Add the various values into the dialog
            self.tCredits.SetValue(self.Datasource.Credits)
            self.tDates.SetValue(self.Datasource.Dates)
            self.tEditors.SetValue("\n".join(self.Datasource.Editors))
            self.tFanzineName.SetValue(self.Datasource.Name.MainName)
            self.tOthernames.SetValue((self.Datasource.Name.OthernamesAsStr("\n")))
            if self.Datasource.FanzineType in self.chFanzineType.Items:
                self.chFanzineType.SetSelection(self.chFanzineType.Items.index(self.Datasource.FanzineType))
            self.chSignificance.SetSelection(self.chSignificance.Items.index(self.Datasource.Significance))
            self.tClubname.SetValue(self.Datasource.Clubname)
            self.tLocaleText.SetValue(self.Datasource.Locale)
            self.tTopComments.SetValue(self.Datasource.TopComments)

            self.cbComplete.SetValue(self.Datasource.Complete)

            self.tServerDirectory.SetValue(serverDir)
            self.tServerDirectory.Disable()

            self.localDir=Settings("ServerToLocal").Get(self.ServerDir)
            if self.localDir is not None:
                self.tLocalDirectory.SetValue(self.localDir)
                self.tLocalDirectory.Disable()

        # Read in the table of local directory to server directory equivalences
        s2l=Settings().Get("Server To Local Table Name")
        with open(s2l, "r") as f:
            l2sLines=f.readlines()
        self.serverNameList: list[str]=[]
        self.localNameList: list[str]=[]
        for line in l2sLines:
            line=line.split("=")
            if len(line) == 2:
                self.localNameList.append(line[0])
                self.serverNameList.append(line[1])

        # Try to fill in the local directory
        if self.tServerDirectory.GetValue() in self.serverNameList:
            self.tLocalDirectory.SetValue(self.localNameList[self.serverNameList.index(self.tServerDirectory.GetValue())])

        self._dataGrid.RefreshWxGridFromDatasource()
        self.MarkAsSaved()
        self.RefreshWindow()
        self.Raise()        # Bring the window to the top
        self.failure=False



    @property
    def Datasource(self) -> FanzineIndexPage:   
        return self._Datasource
    @Datasource.setter
    def Datasource(self, val: FanzineIndexPage):
        self._Datasource=val
        self._dataGrid.Datasource=val


    # This is cleaned of things like (uncredited)
    @property
    def Editors(self) -> str:
        eds=self.tEditors.GetValue()
        if eds.lower() == "(uncredited)" or eds.lower() == "uncredited":
            return ""
        return eds

    @property
    def ServerDir(self) -> str:
        return self.tServerDirectory.GetValue()


    # Look at information available and color buttons and fields accordingly.
    def EnableDialogFields(self):                      
        # See also UpdateDialogComponentEnabledStatus

        # Some things are turned on for both editing an old FIP and creating a new one
        self.tEditors.SetEditable(True)
        self.tDates.SetEditable(True)
        self.chFanzineType.Enabled=True
        self.chSignificance.Enabled=True
        self.tTopComments.SetEditable(True)
        self.tLocaleText.SetEditable(True)
        self.cbComplete.Enabled=True
        self.wxGrid.Enabled=True

        # A few are enabled only when creating a new one (which lasts only until it is uploaded -- then it's an old one)
        if self.IsNewDirectory:
            self.tServerDirectory.SetEditable(True)
            self.tServerDirectory.SetEditable(True)
        else:
            self.tServerDirectory.SetEditable(False)
            self.tServerDirectory.SetEditable(False)

        # The Upload button is enabled only if sufficient information is present
        self.bUpload.Enabled=False
        if len(self.tServerDirectory.GetValue()) > 0 and len(self.tLocalDirectory.GetValue()) > 0 and len(self.tFanzineName.GetValue()) > 0:
            # This is definitely not enough!!
            self.bUpload.Enabled=True

        self.tFanzineName.Enabled=self.IsNewDirectory or self._AllowFanzineNameEdit
        self.tFanzineName.SetEditable(True)

        # On an old directory, we always have a target defined, so we can always add new issues
        self.bAddNewIssues.Enable(True)



    def OnClose(self, event):       
        if not self.OKToClose(event):
            return

        # Save the local directory name/server dir name correspondences table
        s2LDirFilename=Settings().Get("Server To Local Table Name")
        shutil.copyfile(s2LDirFilename, TimestampFilename(s2LDirFilename))        # Make a timestamped backup copy of the table
        Settings("ServerToLocal").Load(s2LDirFilename)
        Settings("ServerToLocal").Put(self.tServerDirectory.GetValue().strip(), self.tLocalDirectory.GetValue().strip())
        Settings("ServerToLocal").Save()

        # Save the window's position
        pos=self.GetPosition()
        Settings("FanzinesEditor positions.json").Put("Index Page Window Position", (pos.x, pos.y))
        size=self.GetSize()
        Settings("FanzinesEditor positions.json").Put("Index Page Window Size", (size.width, size.height))

        self.EndModal(wx.OK)



    # The user has requested that the dialog be closed or wiped and reloaded.
    # Check to see if it has unsaved information.
    # If it does, ask the user if he wants to save it first.
    def OKToClose(self, event) -> bool:             
        if not self.NeedsSaving():
            return True

        if not OnCloseHandling(event, self.NeedsSaving(), "The changes have not been uploaded and will be lost if you exit. Quit anyway?"):
            self.MarkAsSaved()  # The contents have been declared doomed, so mark it as saved so as not to trigger any more queries.
            return True

        return False


    def OnAddNewIssues(self, event):       

        # Call the File Open dialog to select PDF files
        with wx.FileDialog(self,
                           message="Select PDF files to add",
                           defaultDir=self.PDFSourcePath,
                           wildcard="PDF files (*.pdf)|*.pdf",
                           style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST | wx.STAY_ON_TOP) as dlg:

            if dlg.ShowModal() != wx.ID_OK:
                return  # Quit unless OK was pressed.

            files=dlg.GetFilenames()

        if len(files) == 0:     # Should never happen as there's no way to return from dlg w/o selecting pdfs or hitting cancel.  But just in case...
            return

        # Thwe files come back with '//' as the separator which gives troubel downstream. Fix it.
        files=[file.replace("\\", "/") for file in files]

        # We have a list of file names and need to add them to the fanzine index page
        # Start by removing any already-existing empty trailing rows from the datasource
        while self.Datasource.Rows:
            last=self.Datasource.Rows.pop()
            if any([cell != "" for cell in last.Cells]):
                self.Datasource.Rows.append(last)
                break

        # Sort the new files by name and add them to the rows at the bottom, and add them to the changelist
        files.sort()
        oldNrows=self.Datasource.NumRows
        self.Datasource.AppendEmptyRows(len(files))
        for i, file in enumerate(files):
            irow=oldNrows+i
            self.Datasource.Rows[irow].FileSourcePath=files[i]
            self.Datasource.Rows[irow][0]=os.path.basename(files[i])
            self.deltaTracker.Add(file, row=self.Datasource.Rows[irow])

        # Add a PDF column (if needed) and fill in the PDF column and page counts
        self.FillInPDFColumn()
        self.FillInPagesColumn()

        # self._dataGrid.RefreshWxGridFromDatasource(RetainSelection=False)
        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()


    #--------------------------
    # Allow user to change the fanzine's name
    def OnEditFanzineNameClicked(self, event):
        self.tFanzineName.Enabled=True
        self._AllowFanzineNameEdit=True


    #--------------------------
    # Check the rows to see if any of the files is a pdf
    # If a pdf is found possibly add a PDF column and fill the PDF column in for those rows.
    def FillInPDFColumn(self) -> None:              
        iPdf=self.AddOrDeletePDFColumnIfNeeded()
        if iPdf != -1:
            for i, row in enumerate(self.Datasource.Rows):
                if row.IsTextRow or row.IsLinkRow:   # Ignore text and URL rows
                    continue

                filename=row[0]
                if filename.lower().endswith(".pdf"):
                    row[iPdf]="PDF"


    #--------------------------
    # Check the rows to see if any of the files are a pdf
    # If a pdf is found possibly add a PDF column and fill the PDF column in for those rows.
    def FillInPagesColumn(self) -> None:                
        iPages=self.Datasource.ColHeaderIndex("pages")

        if iPages == -1:
            # We need to add a Pages column
            iNotes=self.Datasource.ColHeaderIndex("notes")
            if iNotes == -1:
                LogError("We need to add a Pages column right before the Npotes column, but can't find a Notes column, either. Will ignore, but you really ought to add a Pages column!")
                return
            self.Datasource.InsertColumn2(self.Datasource.NumCols, ColDefinition("Pages"))
            iPages=self.Datasource.ColHeaderIndex("pages")
        # Look through the rows and for each PDF which does not have a page count, add the page count
        for i, row in enumerate(self.Datasource.Rows):
            if row[iPages].strip() == "":   # Don't bother with rows that already have page counts
                # Col 0 always contains the filename. If it's a PDF, get its pagecount and fill in that cell
                filename=row[0]
                if filename.lower().endswith(".pdf"):
                    if row.FileSourcePath != "":
                        pages=GetPdfPageCount(row.FileSourcePath)
                        if pages is not None:
                            self.Datasource.Rows[i][iPages]=str(pages)


    #--------------------------------------------------
    # Decide if we need to have a PDF column and, if so, where it is
    #   If there are no PDF issues, return -1
    #   If all the issue are PDFs, delete the PDF column and return -1
    #   If we still have some non-PDF issues,
    #       Check to see if there is a PDF column.
    #           If not, add one as the far right column
    #           If there is, if necessary, move the column to the far right
    #       Return the index of the column containing the PDF flags or -1 if there is none.
    def AddOrDeletePDFColumnIfNeeded(self) -> int:              
        # Are any or all of the files PDFs?  (We must exclude text lines, empty lines and URL lines)
        noPDFs=not any([row[0].lower().endswith(".pdf") for row in self.Datasource.Rows if row.IsNormalRow])
        allPDFs=all([row[0].lower().endswith(".pdf") for row in self.Datasource.Rows if row.IsNormalRow])
        ipdfcol=self.Datasource.ColHeaderIndex("pdf")

        # We need do nothing in two cases: There are no PDFs or everything is a PDF and there is no PDF column
        # Then return -1
        if allPDFs and ipdfcol == -1:   # If all the lines are PDFs and there is no column labelled PDF, we need do nothing
            return -1
        if noPDFs:      # If there are no PDFs, we need do nothing. (We choose to leave a PDF column is one is already present.)
            return -1

        # If they are all PDFs and there is a PDF column, it is redundant and should be removed
        if allPDFs and ipdfcol != -1:
            self.Datasource.DeleteColumn(ipdfcol)
            return -1

        # OK, there are *some* PDFs.

        # If there is a PDF column, and it is the extreme right column, we're done.
        if ipdfcol == self.Datasource.NumCols-1:
            # We have a PDF column and it is on the right.  All's well. Just return its index.
            return ipdfcol

        # Is there no PDF column, we add one on the right.
        if ipdfcol == -1:
            # Add one on the right and return its index
            self.Datasource.InsertColumn2(self.Datasource.NumCols, ColDefinition("PDF"))
            return self.Datasource.NumCols-1

        # So we have one, but it is in the wrong place, we move it to be the extreme right column
        self.Datasource.MoveColumns(self.Datasource.ColHeaderIndex("pdf"), 1, self.Datasource.NumCols-1)
        return self.Datasource.NumCols-1


    #------------------
    # The only columns *always* present are the Issue name/link, Year, Pages and Notes columns.
    # Other columns will be deleted if they are completely empty and there is more than one row defined.
    # The Mailing column (if any) will be automatically moved to the left of the Notes column.
    def StandardizeColumns(self) -> None:               

        # Standardize the column names
        for cd in self.Datasource.ColDefs:
            cd.Name=CanonicizeColumnHeaders(cd.Name.strip())

        # First look to see if we should be deleting empty columns
        if self.Datasource.NumRows > 1:
            # Look for empty columns to delete
            # We work from the right (high index) to the left to preserve indexes in the event of deletion
            for icol in reversed(range(self.Datasource.NumCols)):
                # Is this a protected column?
                if icol == 0 or icol == 1:      # We never mess with the 1st two columns
                    continue
                if self.Datasource.ColHeaders[icol] in ["Year", "Pages", "Notes"]:
                    continue
                # Nope. Check if it's am empty column
                numFilled=len([1 for x in self.Datasource.Rows if len(x[icol].strip()) > 0])
                if numFilled == 0:
                    self.Datasource.DeleteColumn(icol)

        # Make sure that any Mailing column is to the left of the Notes column
        iMailing=FindIndexOfStringInList2(self.Datasource.ColHeaders, "Mailing")
        if iMailing is not None:
            iNotes=FindIndexOfStringInList2(self.Datasource.ColHeaders, "Notes")
            if iNotes is not None:      # This should never fail!
                if iMailing > iNotes:
                    self.Datasource.MoveColumns(iMailing, 1, iNotes)

        self.RefreshWindow()


    # ------------------
    # Initialize an existing, initializedm main window to empty
    # This also initiazes the datasource
    def ClearMainWindow(self):       

        # Create an empty datasource
        self.Datasource._fanzineList=[]

        # Update the dialog's grid from the data
        self._dataGrid.RefreshWxGridFromDatasource(RetainSelection=False)

        # Fill in the dialog's upper stuff
        self.tFanzineName.SetValue("")
        self.tTopComments.SetValue("")
        self.tEditors.SetValue("")
        self.tDates.SetValue("")
        self.chFanzineType.SetSelection(0)
        self.chSignificance.SetSelection(0)
        self.tClubname.SetValue("")
        self.tLocaleText.SetValue("")
        self.tCredits.SetValue("")
        self.cbComplete.SetValue(False)

        self.Datasource.Credits=Settings().Get("Scanning credits default", default="")

        # Set the signature to the current (empty) state so any change will trigger a request to save on exit
        self.MarkAsSaved()


    #------------------
    # Upload the current FanzineIndexPage (including any added fanzines) to the server
    def OnUpload(self, event):
        Log("OnUpload pressed")
        if self.tServerDirectory.GetBackgroundColour() == Color.Pink:
            wx.MessageBox(f"There is already a directory named {self.tServerDirectory.GetValue()} on the server. Please select another name.", parent=self)
            return

        # Check the dates to make sure that the dated issues all fall into the date range given for the fanzine
        # Date range should be of the form yyyy-yyyy with question marks abounding
        d1, d2=self.DateRange
        # Now check this against all the years in the rows.
        icol=self.Datasource.ColHeaderIndex("year")
        failed=False
        if icol != -1:
            for row in self.Datasource.Rows:
                year=row[icol]
                # Remove question marks and interpret the rest
                year=year.replace("?", "")
                year=Int0(year)
                if year > 0:  # Ignore missing years
                    if year < d1 or year > d2:
                        failed=True
                        break
            if failed:
                dlg=wx.MessageDialog(self, "Warning: One or more of the years in the table are outside the date range given for this fanzine. Continue the upload?", "Date Range Warning",
                                     wx.YES_NO|wx.ICON_QUESTION)
                result=dlg.ShowModal()
                dlg.Destroy()
                if result != wx.ID_YES:
                    return

        # Save the fanzine's values to return to the main fanzines page.
        cfl=ClassicFanzinesLine()
        cfl.Issues=self.Datasource.NumRows
        cfl.Editors=self.tEditors.GetValue().replace("\n", "<br>")
        cfl.ServerDir=self.tServerDirectory.GetValue()
        cfl.Name=FanzineNames(self.tFanzineName.GetValue(), self.tOthernames.GetValue())
        cfl.Dates=self.tDates.GetValue()
        cfl.Type=self.chFanzineType.Items[self.chFanzineType.GetSelection()]
        cfl.Significance=self.chSignificance.Items[self.chSignificance.GetSelection()]
        cfl.Clubname=self.tClubname.GetValue()
        cfl.Complete=self.cbComplete.GetValue()
        cfl.Updated=datetime.now()
        if self.IsNewDirectory:
            cfl.Created=datetime.now()      # We only update the created time when were actually creating something...
        cfl.TopComments=self.tTopComments.GetValue()
        cfl.Country=self.tLocaleText.GetValue()

        # We may need to move the files
        localDirectoryRootPath=Settings().Get("Local Directory Root Path", default="")
        localDirectoryPath=""
        localDirectoryName=self.tLocalDirectory.GetValue()
        moveFilesAfterUploading=False
        Log(f"{localDirectoryRootPath=}")
        Log(f"{localDirectoryPath=}")
        Log(f"{localDirectoryName=}")

        # If a local directory root path exists, then we will move files there once they are uploaded
        if localDirectoryRootPath != "":
            moveFilesAfterUploading=True
            localDirectoryPath=localDirectoryRootPath+"/"+localDirectoryName

            # If this is a new fanzine, create the local directory if necessary
            if self.IsNewDirectory:
                if not os.path.exists(localDirectoryPath):
                    Log(f"mkdir({localDirectoryPath})")
                    os.mkdir(localDirectoryPath)


        Log("About to start ModalDialogManager")
        with ModalDialogManager(ProgressMessage2, f"Uploading FanzineIndexPage {self.ServerDir}", parent=self) as pm:
            Log(f"Uploading Fanzine Index Page: {self.ServerDir}")
            self.failure=False

            # During the test phase, we have a bogus root directory and the fanzine's directory may noy yet have an index file to be backed up.
            # So, when we edit a new fanzine, we copy it from the true root to the bogus root, giving us an index file to back up.
            # This will go away when we dispense with the bogus root.
            if self.RootDir.lower() != "fanzines":
                if not FTP().FileExists(f"/{self.RootDir}/{self.ServerDir}/index.html"):    # Check to see if the bogus root already has an index file
                    # If not, copy the existing index.htl file on /fanzines/ in to the test root.
                    # Note that this will create the server directory if it does not already exist.
                    if not FTP().CopyFile(f"/fanzines/{self.ServerDir}", f"/{self.RootDir}/{self.ServerDir}", "index.html", Create=True):
                        wx.MessageBox(f"Attempt to copy index.html from /fanzines/{self.ServerDir} to /{self.RootDir}/{self.ServerDir} failed with error message {FTP().LastMessage}.")

            # Make a dated backup copy of the existing index page
            ret=FTP().BackupServerFile(f"/{self.RootDir}/{self.ServerDir}/index.html")
            if not ret:
                Log(f"Could not make a backup copy: {self.RootDir}/{self.ServerDir}/{TimestampFilename('index.html')} because {FTP().LastMessage}")
                self.failure=True
                return
            FTPLog().AppendItemVerb("backup index.html", f"{Tagit("RootDir", self.RootDir)} {Tagit("ServerDir", self.ServerDir)}", Flush=True)

            pm.Update(f"Uploading new Fanzine Index Page: {self.ServerDir}")

            def MoveToLocalDirectory(sourcepath: str, localdirpath: str, filename: str):
                if filename is None or filename == "":
                    return  # Nothing to do here, move along...
                # if the target directory does not exist, create it
                if not os.path.exists(localdirpath):
                    os.makedirs(localdirpath)
                Log(f"MoveToLocalDirectory({sourcepath}, {localdirpath}, {filename})")
                shutil.move(sourcepath+"/"+filename, localdirpath+"/"+filename)
                Log(f"shutil.move({sourcepath+"/"+filename}, {localdirpath+"/"+filename})")

            # Now execute the delta list on the files.
            failure=False
            Log("Begin delta processing.")
            # Due to a very reasonable (but as it turns out unhelpful) decision, rows
            for delta in self.deltaTracker.Deltas:

                match delta.Verb:
                    case "add" | "replace":
                        # Add a new file to the server or Replace a file already on server.  (We ignore the old file. It gets overwritten if the filename is the same or just left otherwise.)
                        assert delta.Row is not None
                        sourceFilename=delta.Row[0]     # Need to allow for edits in col 0 after add, but before upload
                        # Note that we pass in cfl and Row because the row is likely to have been updated after the DeltaAdd is created, and we want to capture those updates
                        delta.Uploaded=self.UpdateAndUpload(delta.Row, sourceFilename, delta.SourcePath, editors=cfl.Editors, mainName=cfl.Name.MainName, country=cfl.Country, pm=pm)
                        if delta.Uploaded:
                            if moveFilesAfterUploading:
                                MoveToLocalDirectory(delta.SourcePath, localDirectoryPath, sourceFilename)

                        text=f'{Tagit("IssueName", delta.Row[1])} ' + \
                                        f'{Tagit("ServerDir", self.ServerDir)} ' +\
                                        f'{Tagit("RootDir", self.RootDir)} ' +\
                                        f'{Tagit("issuenum", IssueNumber(delta.Row, self.Datasource.ColDefs))} '+\
                                        f'{Tagit("date", DateFmt(delta.Row, self.Datasource.ColDefs))} '+\
                                        f'{Tagit("fanzinename", self.Datasource.Name.MainName)} '+\
                                        f'{Tagit("editor", Editors(delta.Row, self.Datasource.ColDefs, self.Editors))} '+\
                                        f'{Tagit("fanzinetype", self.Datasource.FanzineType)} '+\
                                        f'{Tagit("clubname", self.Datasource.Clubname)} '+\
                                        f'{Tagit("SourcePath", delta.SourcePath)} '+\
                                        f'{Tagit("SourceFilename", sourceFilename)} '
                        if delta.Verb == "replace":
                            text+=f"{Tagit("Oldame", delta.OldFilename)}"
                        FTPLog().AppendItemVerb(delta.Verb, text, Flush=True)

                    case "delete":
                        # Delete a file on the server
                        filenameOnServer=delta.ServerFilename
                        serverpathfile=f"/{self.RootDir}/{self.ServerDir}/{filenameOnServer}"
                        if filenameOnServer.strip() != "":
                            pm.Update(f"Deleting {serverpathfile} from server")
                            delta.Uploaded= FTP().DeleteFile(serverpathfile)
                            if not delta.Uploaded:
                                dlg=wx.MessageDialog(self, f"Unable to delete {serverpathfile} because {FTP().LastMessage}", "Continue?", wx.YES_NO|wx.ICON_QUESTION)
                                result=dlg.ShowModal()
                                dlg.Destroy()
                                if result != wx.ID_YES:
                                    break
                        if delta.Uploaded:
                            FTPLog().AppendItemVerb("delete", f'{Tagit("ServerDirName", delta.ServerDirName)} {Tagit("ServerFilename", delta.ServerFilename)}  '+
                                                        f'{Tagit("fanzinename", self.Datasource.Name.MainName)}'+
                                                        f'{Tagit("fanzinetype", self.Datasource.FanzineType)}'+
                                                        f'{Tagit("clubname", self.Datasource.Clubname)}'+
                                                        f"{Tagit("IssueName", delta.Row[1])}  {Tagit("RootDir", self.RootDir)}", Flush=True)

                    case "rename":
                        # Rename file on the server
                        assert delta.Row is not None
                        assert len(delta.Row[1]) > 0
                        oldserverpathfile=f"/{self.RootDir}/{self.ServerDir}/{delta.OldFilename}"
                        newserverpathfile=f"/{self.RootDir}/{self.ServerDir}/{delta.Row[0]}"
                        pm.Update(f"Renaming {oldserverpathfile} as {newserverpathfile}")
                        delta.Uploaded=FTP().Rename(oldserverpathfile, newserverpathfile)
                        if not delta.Uploaded:
                            dlg=wx.MessageDialog(self, f"Unable to rename {oldserverpathfile} to {newserverpathfile} because {FTP().LastMessage}", "Continue?", wx.YES_NO|wx.ICON_QUESTION)
                            result=dlg.ShowModal()
                            dlg.Destroy()
                            if result != wx.ID_YES:
                                break
                        if delta.Uploaded:
                            FTPLog().AppendItemVerb("rename", f'{Tagit("Oldname", delta.OldFilename)} {Tagit("IssueName", delta.Row[1])} '+
                                                        f'{Tagit("fanzinename", self.Datasource.Name.MainName)}'+
                                                        f'{Tagit("fanzinetype", self.Datasource.FanzineType)}'+
                                                        f'{Tagit("clubname", self.Datasource.Clubname)}'+
                                                        f'{Tagit("Newname", delta.Row[0])} {Tagit("ServerDirName", delta.ServerDirName)} {Tagit("RootDir", self.RootDir)}', Flush=True)

            c=sum([1 for x in self.deltaTracker.Deltas if not x.Uploaded and not x.ServerFilename.strip() == ""])
            if c > 0:
                dlg=wx.MessageDialog(self, f"{Pluralize(c, "upload")} failed")
                dlg.ShowModal()

            FTPLog.Flush()

            # Delete all deltas which were uploaded
            oldDeltas=self.deltaTracker
            self.deltaTracker=DeltaTracker()
            for delta in oldDeltas.Deltas:
                if not delta.Uploaded:
                    self.deltaTracker.Deltas.append(delta)

            # Put the FanzineIndexPage on the server as an HTML file
            Log(f"Datasource.PutFanzineIndexPage({self.RootDir}, {self.ServerDir})")
            if not self.Datasource.PutFanzineIndexPage(self.RootDir, self.ServerDir):
                wx.MessageBox(f"Upload of index file failed")
                FTPLog().AppendItemVerb("upload FIP partial ended", f"{Tagit("RootDir", self.RootDir)} {Tagit("ServerDir", self.ServerDir)}", Flush=True)
                self.failure=True
                Log("Failed\n")
                return

            Log("All uploads succeeded.")
            FTPLog().AppendItemVerb("upload FIP succeeded", f"{Tagit("RootDir", self.RootDir)} {Tagit("ServerDir", self.ServerDir)}", Flush=True)

            self.CFL=cfl

            self._uploaded=True
            self.MarkAsSaved()

            # Once a new fanzine has been uploaded, the server and local directories are no longer changeable
            self.IsNewDirectory=False
            self._allowManualEditOfServerDirectoryName=False
            self._manualEditOfServerDirectoryNameBegun=False
            self._allowManualEntryOfLocalDirectoryName=False
            self._manualEditOfLocalDirectoryNameBegun=False
            self._AllowFanzineNameEdit=False

            self.UpdateDialogComponentEnabledStatus()


    # Update the new pdf's metadata and then upload it
    def UpdateAndUpload(self, row: FanzineIndexPageTableRow, sourcefilename: str, sourcepath: str, editors: str="", mainName: str="", country: str="", pm: ProgressMessage2|None=None) -> bool:
        # Note that we passed in Row because the row is likely to have been updated after the DeltaAdd is created, and we want to capture those updates
        _, ext=os.path.splitext(sourcefilename)
        isPdf=ext.lower() == ".pdf"
        # If this is a PDF, we need to update the metadata
        if isPdf:
            if "Editor" in self.Datasource.ColDefs:  # Editor in the row overrides editors for the whole zine series
                editors=row[self.Datasource.ColDefs.index("Editor")]
            copyfilepath=SetPDFMetadata(sourcepath+"/"+sourcefilename, row, self.Datasource.ColDefs, editors=editors, mainName=mainName, country=country)
            assert copyfilepath != ""
        else:
            copyfilepath=os.path.join(sourcepath, sourcefilename)

        serverpathfile=f"/{self.RootDir}/{self.ServerDir}/{sourcefilename}"


        pm.Update(f"Uploading {sourcefilename} as {sourcefilename}")
        Log(f"FTP().PutFile({copyfilepath}, {serverpathfile})")
        if not FTP().PutFile(copyfilepath, serverpathfile):
            dlg=wx.MessageDialog(self, f"Unable to upload {copyfilepath} because {FTP().LastMessage}", "Continue?", wx.YES_NO|wx.ICON_QUESTION)
            result=dlg.ShowModal()
            dlg.Destroy()
            if result != wx.ID_YES:
                return False

        if isPdf:
            # If this is a PDF, then we created a temporary file when adding the metadata. Delete it now.
            del copyfilepath
        return True

    # Take the date range (if any) on the Fanzine Index Page and return a years start, end tuple
    # Return 1900, 2200 for missing information
    # Should handle:
    # 1953-55
    # 1953-
    # 1950s
    # 1953?-1965?
    # 1953-present
    # And others like this.  It tries its best to make sense of the data.
    @property
    def DateRange(self) -> tuple[int, int]:
        # Pull the date range text from the dialog's dates range box
        dates=self.tDates.GetValue().lower()

        # Remove question marks and spaces, as they tell us nothing.  Then split on the hyphen
        dates=dates.replace("?", "").replace(" ", "").strip()
        if dates == "":
            return 1900, 2200   # Defaults

        #-------
        # Define a function to turn valid years into int, and to deal with 50 (=1950) and 20 (=2020)
        def YearToInt(s: str) -> int:
            d=Int0(s)
            if d == 0:
                return 0
            if d < 100:
                if d < 34:  # 01-33 --> 2001-2033
                    return 2000+d
                return 1900+d  # 34-99 --> 1934-1999
            return d

        # If there is no hyphen, we then the single date defines a range (e.g., 1953, 1950s etc)
        if "-" not in dates:
            d1=Int(dates)
            if d1 is not None:
                # It's a single numbers, so apparently, we have just a single year which defines that year as the range
                return d1, d1
            # It's somwething that's not a number.  Try interpreting it.
            if dates[-1] == "s":
                # This ends in "s", it must either be something like 1950s or garbage
                d1=YearToInt(dates[:-1])
                if d1 > 1900:
                    d1=10*floor(d1/10)
                return d1, d1+10    # We'll assume this is just a decade.  Maybe more subtlety later?

            # That's all the options for now.
            return 1900, 2200

        # Ok, there is a hyphen, so we need to interpret two values to be a range
        date1, date2=dates.split("-")
        # The dates should be of one of these forms:
        #       yyyy, <empty>, 1950s, present
        #       empty is interpreted as 1920 or 2100, depending on which side of the hyphen it's on
        #       present is interpreted as, well, now.
        #       something like 1950s is interpreted as the start or end of the decade depending on which side of the hyphen it's on
        d1=YearToInt(date1)
        if date2.lower() == "present":
            d2=datetime.now().year+1
        if len(date1) > 0 and date1[-1] == "s":
            # This ends in "s", it must either be something like 1950s or garbage
            d1=YearToInt(date1[:-1])
            if d1 > 1900:
                d1=10*floor(d1/10)

        # Now check date 2
        d2=YearToInt(date2)
        if len(date2) > 0 and date2[-1] == "s":
            # This ends in "s", it must either be something like 1950s or garbage.  1940s-1950s Is interpreted as 1940-1959
            d2=YearToInt(date2[:-1])
            if d2 > 1900:
                d2=10*ceil(d2/10)+9
        # Now change zero dates into 1900 and 2200, respectively, so that zero matches everything
        if d1 == 0:
            d1=1900
        if d2 == 0:
            d2=2200
        return d1, d2


    def UpdateNeedsSavingFlag(self):       
        s="Editing "+self.ServerDir
        if self.NeedsSaving():
            s=s+" *"        # Append a change marker if needed
        self.SetTitle(s)


    def UpdateDialogComponentEnabledStatus(self):       # (See also EnableDialogFields)
        # The server directory can be edited iff this is a new directory
        self.tServerDirectory.Enabled=self.IsNewDirectory

        def IsEmpty(s: str) -> bool:
            return s.strip() == ""

        # The Upload button is enabled iff certain text boxes have content and there's at least one fanzine
        enable=True
        if IsEmpty(self.tServerDirectory.GetValue()) or IsEmpty(self.tFanzineName.GetValue()) or IsEmpty(self.tLocalDirectory.GetValue()):
            enable=False
        if len(self.Datasource.Rows) == 0:
            enable=False
        self.bUpload.Enabled=enable

        # The local directory text box is editable in a new directory, but not in an existing one
        self.tLocalDirectory.Enabled=len(self.tLocalDirectory.GetValue()) == 0 or self.IsNewDirectory

        # The Clubname field is editable iff the fanzine type is "Clubzine"
        self.tClubname.Enabled="Clubzine" == self.chFanzineType.Items[self.chFanzineType.GetSelection()]


    def RefreshWindow(self, DontRefreshGrid: bool=False)-> None:       
        self.UpdateNeedsSavingFlag()
        self.UpdateDialogComponentEnabledStatus()

        if not DontRefreshGrid:
            self._dataGrid.RefreshWxGridFromDatasource()
        self.EnableDialogFields()


    # ----------------------------------------------
    # Used to determine if anything has been updated
    def Signature(self) -> int:       
        return self.Datasource.Signature()


    def MarkAsSaved(self):       
        self._signature=self.Signature()
        self.UpdateNeedsSavingFlag()


    def NeedsSaving(self):       
        return self._signature != self.Signature()


    # This method updates the local directory name by computing it from the fanzine name.  It only applies when creating a new fanzine index page
    def OnFanzineNameChar(self, event):
        # Now do routine character handling
        event.Skip()

        # Requests from Edie:
        # Suppress leading articles, eg The or A
        # Remove non-letter characters, eg apostrophes or commas
        # Local directories all in caps Server directories with first letters of words capitalized
        # Spaces around dashes suppressed (e.g. fanzine title of: Bangsund - Other Publications)
        # Ability to manually add text to the server and local directories (e.g. fanzine title: Cinder ; server directory Cinder-Williams)
        # Ability to manually delete text for the server and local directories (e.g. fanzine title: Prolapse / Relapse ; server directory Prolapse)

        # Pick up the current value of the fanzine name field
        fname, cursorloc=ProcessChar(self.tFanzineName.GetValue(), event.GetKeyCode(), self.tFanzineName.GetInsertionPoint())

        # Log(f"OnFanzineNameChar: Local directory name updated to '{fname}'")

        self.UpdateServerAndLocalDirNames(fname)


    def UpdateServerAndLocalDirNames(self, fname):
        # If this is a new fanzine, and if the user has not overridden the default server directory name by editing it himself, update the Server Directory name
        # Log(f"OnFanzineNameChar: {self.tServerDirectory.Enabled=}    {self._manualEditOfServerDirectoryNameBegun=}'")
        if self.tServerDirectory.Enabled and not self._manualEditOfServerDirectoryNameBegun:
            # Strip leading "The", etc
            sname=RemoveArticles(fname).strip()
            if len(sname) > 0:
                sname=re.sub("[^a-zA-Z0-9-]+", "_", sname)  # Replace all spans of not-listed chars with underscore
                sname=sname.replace(" ", "_")
            self.tServerDirectory.SetValue(sname)
            # Log(f"OnFanzineNameChar: Server directory name updated to '{sname}'")
        # If this is a new fanzine, and if the user has not overridden the default local directory name by editing it himself, update the Local Directory name
        # Log(f"OnFanzineNameChar: {self.tLocalDirectory.Enabled=}    {self._manualEditOfLocalDirectoryNameBegun=}'")
        if self.tLocalDirectory.Enabled and not self._manualEditOfLocalDirectoryNameBegun:
            # Strip leading "The", etc
            lname=RemoveArticles(fname).strip()
            lname=re.sub("[^a-zA-Z0-9-]+", "_", lname)  # Replace all spans of not-listed chars with underscore
            lname=lname.strip("_")  # Do not start or end names with underscores
            lname=lname.upper()
            self.tLocalDirectory.SetValue(lname)
            self.ColortLocalDirectory(lname)
            #Log(f"OnFanzineNameChar: Local directory name updated to '{lname}'")


    def OnFanzineNameText(self, event):

        self.ColorFanzineAndServerDirBoxes()

        self.Datasource.Name.MainName=self.tFanzineName.GetValue()
        Log(f"OnFanzineNameText: Fanzine name updated to '{self.Datasource.Name.MainName}'")
        self.UpdateServerAndLocalDirNames(self.Datasource.Name.MainName)
        self.RefreshWindow(DontRefreshGrid=True)
        # Note that we don;t call self.Skip() so we don't use default processing for this event


    def OnServerDirectoryChar(self, event):
        Log(f"OnServerDirectoryChar: triggered")
        if not self.IsNewDirectory:
            return

        fname, cursorloc=ProcessChar(self.tServerDirectory.GetValue(), event.GetKeyCode(), self.tServerDirectory.GetInsertionPoint())
        self.tServerDirectory.SetValue(fname)
        self.tServerDirectory.SetInsertionPoint(cursorloc)

        self._manualEditOfServerDirectoryNameBegun=True

        self.ColorFanzineAndServerDirBoxes()

        Log(f"OnServerDirectoryChar: updated to '{fname}'")
        return


    def OnButtonClickCopyServerDir(self, event):
        pyperclip.copy(self.tServerDirectory.GetValue())
        event.Skip()


    def OnLocalDirectoryChar( self, event ):
        Log(f"OnLocalDirectoryChar: triggered")
        if not self.IsNewDirectory:     # Only for new fanzines can the local directory name be updated
            return

        fname, cursorloc=ProcessChar(self.tLocalDirectory.GetValue(), event.GetKeyCode(), self.tLocalDirectory.GetInsertionPoint())
        self.tLocalDirectory.SetValue(fname)
        self.tLocalDirectory.SetInsertionPoint(cursorloc)

        self.ColortLocalDirectory(fname)

        self._manualEditOfLocalDirectoryNameBegun=True
        Log(f"OnLocalDirectoryChar: updated to '{fname}'")
        return


    def ColorFanzineAndServerDirBoxes(self):
        if self.IsNewDirectory and self._existingFanzinesServerDirs is not None and self.ServerDir in self._existingFanzinesServerDirs:
            self.tServerDirectory.SetBackgroundColour(Color.Pink)
            #self.tFanzineName.SetBackgroundColour(Color.Pink)
        else:
            self.tServerDirectory.SetBackgroundColour(Color.White)
            #self.tFanzineName.SetBackgroundColour(Color.White)


    # Color the field pink if this newly-entered name is an existing directory
    def ColortLocalDirectory(self, fname):

        localDirectoryRootPath=Settings().Get("Local Directory Root Path")
        if localDirectoryRootPath is None:
            return      # If there's no local directory supplied, there's nothing to do.

        coloritpink=False
        if localDirectoryRootPath != "":
            localDirectoryPath=localDirectoryRootPath+"/"+fname
            if os.path.isdir(localDirectoryPath):
                coloritpink=True
        if coloritpink:
            self.tLocalDirectory.SetBackgroundColour(Color.Pink)
        else:
            self.tLocalDirectory.SetBackgroundColour(Color.White)


    def OnOthernamesText(self, event):
        self.Datasource.Name.Othernames=self.tOthernames.GetValue().split("\n")


    def OnEditorsText(self, event):
        self.Datasource.Editors=self.tEditors.GetValue()
        # Remove trailing newline
        if len(self.Datasource.Editors) > 0 and self.Datasource.Editors[-1] == "\n":
            self.Datasource.Editors=self.Datasource.Editors[:-1]
        self.RefreshWindow(DontRefreshGrid=True)


    def OnDatesText(self, event):       
        self.Datasource.Dates=self.tDates.GetValue()
        self.RefreshWindow()


    def OnFanzineTypeSelect(self, event):       
        self.Datasource.FanzineType=self.chFanzineType.GetItems()[self.chFanzineType.GetSelection()]
        if self.Datasource.FanzineType.lower() != "clubzine":   # If the fanzine type is changed to anything but clubzine, erase the clubname field
            self.Datasource.Clubname=""
            self.tClubname.SetValue("")
        self.RefreshWindow(DontRefreshGrid=True)

    def OnSignificanceSelect(self, event):
        self.Datasource.Significance=self.chSignificance.GetItems()[self.chSignificance.GetSelection()]
        self.RefreshWindow(DontRefreshGrid=True)


    def OnClubname(self, event):
        self.Datasource.Clubname=self.tClubname.GetValue()
        self.RefreshWindow(DontRefreshGrid=True)


    #------------------
    def OnTopCommentsText(self, event):       
        if self.Datasource.TopComments is not None and len(self.Datasource.TopComments) > 0:
            self.Datasource.TopComments=self.tTopComments.GetValue()
        else:
            self.Datasource.TopComments=self.tTopComments.GetValue().strip()

        self.RefreshWindow(DontRefreshGrid=True)

    # ------------------
    def OnCheckComplete(self, event):      
        self.Datasource.Complete=self.cbComplete.GetValue()
        Log(f"OnCheckComplete(): {self.Datasource.Complete=}")
        self.RefreshWindow(DontRefreshGrid=True)

    #------------------
    def OnLocaleText(self, event):       
        self.Datasource.Locale=self.tLocaleText.GetValue().split("\n")
        self.RefreshWindow(DontRefreshGrid=True)

    #------------------
    def OnCreditsText(self, event):
        self.Datasource.Credits=self.tCredits.GetValue().strip()
        self.RefreshWindow(DontRefreshGrid=True)

    #-------------------
    def OnKeyDown(self, event):       
        self._dataGrid.OnKeyDown(event) # Pass event to WxDataGrid to handle
        self.UpdateNeedsSavingFlag()

    #-------------------
    def OnKeyUp(self, event):       
        self._dataGrid.OnKeyUp(event) # Pass event to WxDataGrid to handle

    #------------------
    def ColorSingleCellByValueOverride(self, icol: int, irow: int) -> None:

        # In normal rows and link rows, col 1 must be filled in
        if icol == 1:
            if self.Datasource.Rows[irow].IsNormalRow or self.Datasource.Rows[irow].IsLinkRow:
                if self.Datasource.Rows[irow][0].strip() != "":
                    if self.Datasource.Rows[irow][1].strip() == "":
                        self._dataGrid.SetCellBackgroundColor(irow, 1, Color.Pink)

        # The year, if filled in, must be within the range of dates specified by the FIP
        if self.Datasource.ColDefs[icol].Name == "Year":
            d1, d2=self.DateRange
            year=self.Datasource.Rows[irow][icol]
            # Remove question marks and interpret the rest
            year=year.replace("?", "")
            year=Int0(year)
            if year > 0:        # Ignore missing years
                if year < d1 or year > d2:
                    self._dataGrid.SetCellBackgroundColor(irow, icol, Color.Pink)

    #------------------
    # Handle a change to a cell.  This is not done for each character entered, but only at the end.
    def OnGridCellChanged(self, event):       
        # If the change is to col 0 -- the URL -- then we need to queue a Delta so the change actually gets made. Save the old name.
        oldURL=""
        if event.GetCol() == 0:
            oldURL=self.Datasource.Rows[event.GetRow()][0]

        # If this is cell 0 of a link line, remove any HTML decoration, leaving the bare URL
        irow=event.GetRow()
        icol=event.GetCol()
        if self.Datasource.Rows[irow].IsNormalRow and icol == 0:
            val=self.Datasource.Rows[irow][icol].strip()
            m=re.match(r"http:=(.*)$", val, flags=re.IGNORECASE)
            if m is not None:
                val=m.groups()[0]
                self.Datasource.Rows[irow][icol]=val.removeprefix("//")

        self._dataGrid.OnGridCellChanged(event)  # Pass event handling to WxDataGrid

        # If needed, queue the Delta
        if icol == 0 and self.Datasource.Rows[irow].IsNormalRow:
            # If we are changing the cell's text from one filename to another, we do a rename of the file on the server.
            # But if we are inserting an external URL, there is no need to create a rename on the old contents
            newurl=self.Datasource.Rows[irow][icol]
            if "http:" not in newurl.lower() and "//" not in newurl:
                self.deltaTracker.Rename(oldURL, newurl, serverDirName=self.ServerDir, row=self.Datasource.Rows[irow])

        if event.GetCol() == 0:    # If the Filename changes, we may need to update the PDF and the Pages columns
            self.FillInPDFColumn()
            self.FillInPagesColumn()
        self.RefreshWindow()

    #------------------
    def OnGridCellRightClick(self, event):       
        # Do generic RMB on grid processing
        self._dataGrid.OnGridCellRightClick(event, self.m_GridPopup)

        # Call the RMB handler
        self.RMBHandler(event, True)

    #--------------------------
    def OnGridEditorShown(self, event):      
        # Use Generic handling
        self._dataGrid.OnGridEditorShown(event)

    # ------------------
    def OnGridLabelLeftClick(self, event):       
        self._dataGrid.OnGridLabelLeftClick(event)

    #------------------
    def OnGridLabelRightClick(self, event):       
        # Do generic RMB on grid processing
        self._dataGrid.OnGridCellRightClick(event, self.m_GridPopup)

        # Call the RMB handler
        self.RMBHandler(event, False)


    # RMB click handling for grid and grid label clicks
    def RMBHandler(self, event, isGridCellClick: bool):       

        # Everything remains disabled when we're outside the defined columns
        if self._dataGrid.clickedColumn >= self.Datasource.NumCols:    # Click is outside populated columns.
            return
        if self._dataGrid.clickedColumn < 0:  # Click is on row number
            return
        if self._dataGrid.clickedRow >= self.Datasource.NumRows:      # Click is outside the populated rows
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
                    Enable("Merge Adjacent Rows")

        # There are RMB actions which happen only for a click on col 0
        if self._dataGrid.clickedColumn == 0:
            # If cell 0 contains the URL of a PDF or an HTML page, allow it to be replaced by a PDF.
            irow=self._dataGrid.clickedRow
            if irow < self.Datasource.NumRows:
                if self.Datasource.Rows[irow].IsNormalRow:
                    Enable("Replace w/new PDF")
                # If cell 0 contains a PDF, allow it to be renamed
                if len(self.Datasource.Rows[irow][0]) > 0 and ".pdf" in self.Datasource.Rows[irow][0].lower():
                    Enable("Rename PDF on Server")

        if not isGridCellClick:
            Enable("Sort on Selected Column") # It's a label click, so sorting on the column is always OK

        if self._dataGrid.clipboard is not None:
            Enable("Paste")

        if self._dataGrid.clickedRow != -1:
            Enable("Delete Row(s)")
            Enable("Insert a Row")

        # We enable the Add Column to Left item if we're on a column to the left of the first -- it can be off the right and a column will be added to the right
        if self._dataGrid.clickedColumn > 1:
            Enable("Insert Column to Left")

        # We only allow a column to be deleted if the cursor is in a column with more than one highlighted cell and no highlighted cells in other columns.
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
            Enable("Insert a Link line")

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

        if self.Datasource.ColDefs[self._dataGrid.clickedColumn].Preferred == "Date" or \
                self.Datasource.ColDefs[self._dataGrid.clickedColumn].Preferred == "Dates" or \
                self.Datasource.ColDefs[self._dataGrid.clickedColumn].Preferred == "(Date)" or \
                self.Datasource.ColDefs[self._dataGrid.clickedColumn].Preferred == "(Dates)":
            if self._dataGrid.clickedRow == -1:
                Enable("Parse Date into separate columns")

        # We only enable Extract Editor when we're in the Notes column and there's something to extract.
        if self.Datasource.ColDefs[self._dataGrid.clickedColumn].Preferred == "Notes":
            # We only want to enable the "Extract Editor" item if the Notes column contains edited by information
            for row in self.Datasource.Rows:
                note=row[self._dataGrid.clickedColumn].lower()
                if "edited by" in note or \
                        "editor " in note:
                    Enable("Extract Editor")
                    break

        # If this is a cell in a column tagged as IsEditable=Maybe, enable the "allow editing" popup menu item
        if self.Datasource.ColDefs[self._dataGrid.clickedColumn].IsEditable == IsEditable.Maybe:
            Enable("Allow Editing")

        Enable("Tidy Up Columns")
        Enable("Insert a Text Line")

        if (self.Datasource.ColHeaders[self._dataGrid.clickedColumn] == "Editor" or self.Datasource.ColHeaders[self._dataGrid.clickedColumn] == "Editors") and len(self.Editors) > 0:
            Enable("Propagate Editor")

        # Pop the menu up.
        self.PopupMenu(self.m_GridPopup)


    # ------------------
    # Extract 'scanned by' information from the Notes column, if any
    def ExtractScannerFromNotes(self):       

        if "Notes" not in self.Datasource.ColDefs:
            return
        notesCol=self.Datasource.ColDefs.index("Notes")

        # Start by adding a Scanned column to the right of the Notes column, if needed. (We check to see if one already exists.)
        if "Scanned" not in self.Datasource.ColDefs:
            # Add the Scanned column if needed
            self._dataGrid.InsertColumnMaybeQuery(notesCol, name="Scanned")

        scannedCol=self.Datasource.ColDefs.index("Scanned")
        notesCol=self.Datasource.ColDefs.index("Notes")

        # Now parse the notes looking for scanning information
        # Scanning Info will look like one of the four prefixes (Scan by, Scanned by, Scanned at, Scanning by) followed by
        #   two capitalized words
        #   or a capitalized word, then "Mc", then a capitalized word  (e.g., "Sam McDonald")
        #   or a capitalized word, then "Mac", then a capitalized word  (e.g., "Anne MacCaffrey")
        #   or "O'Neill"
        #   or a capitalized word, then a letter followed by a period, then a capitalized word  (e.g., "John W. Campbell")
        #   or a capitalized word followed by a number
        pattern=(
            r"[sS](can by|cans by|canned by|canned at|canning by) ([A-Z][a-z]+) ("   # A variation of "scanned by" followed by a first name;
            #   This all followed by one of these:
            r"(?:Mc|Mac|O')[A-Z][a-z]+|"     # Celtic names
            r"[A-Z]\.[A-Z][a-z]+|"   # Middle initial
            r"[A-Z][a-z]+|" # This needs to go last because it will ignore characters after it finds a match (with "Sam McDonald" it matches "Sam Mc")
            r"[0-9]+)"       # Boskone 23
        )
        pattern=r'[sS](?:can by|cans by|canned by|canned at|canning by) ([A-Z][a-z]+ (?:Mc|Mac|O\'\s?)?[A-Z][a-z]+|[A-Z]\\.[A-Z][a-z]+|[A-Z][a-z]+|[0-9]+)'

        for i in range(self.Datasource.NumRows):
            row=self.Datasource.Rows[i]
            note=row[notesCol]
            m=re.search(pattern, note)
            if m is not None:
                # Append the matched name to scanned
                if len(row[scannedCol]) > 0:
                    row[scannedCol]+="; "     # Use a semicolon separator if there was already something there
                row[scannedCol]+=m.groups()[0]

                note=re.sub(pattern, "", note)  # Delete the matched text from the note
                note=re.sub("^([ ,]*)", "", note)          # Now remove leading and trailing spans of spaces and commas from the note.
                note=re.sub("([ ,]*)$", "", note)
                row[notesCol]=note

        # And redisplay
        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()


    def OnPopupCopy(self, event):       
        self._dataGrid.OnPopupCopy(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow(DontRefreshGrid=True)


    def OnPopupPaste(self, event):       
        self._dataGrid.OnPopupPaste(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()


    def OnPopupEraseSelection(self, event):       
        self._dataGrid.OnPopupEraseSelection(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()


    def OnPopupDelCol(self, event):       
        if self.Datasource.Element.CanDeleteColumns:
            self._dataGrid.DeleteSelectedColumns() # Pass event to WxDataGrid to handle
        self.RefreshWindow()


    def OnPopupDelRow(self, event):       
        # Add the deletions to the delta tracker
        top, _, bottom, _=self._dataGrid.SelectionBoundingBox()
        if top == -1 or bottom == -1:
            top=self._dataGrid.clickedRow
            bottom=self._dataGrid.clickedRow
        urlCol=self.Datasource.ColHeaderIndex("Link")
        assert urlCol != -1
        for irow in range(top, bottom+1):
            if self.Datasource.Rows[irow].IsNormalRow and not self.Datasource.Rows[irow].IsEmptyRow:
                self.deltaTracker.Delete(serverDirName=self.ServerDir, row=self.Datasource.Rows[irow])

        self._dataGrid.DeleteSelectedRows() # Pass event to WxDataGrid to handle
        self.RefreshWindow()


    def OnPopupInsertRow(self, event):       
        irow=self._dataGrid.clickedRow
        # Insert an empty row just before the clicked row
        rows :[FanzineIndexPageTableRow]=[]
        if irow > 0:
            rows=self.Datasource.Rows[:irow]
        rows.append(FanzineIndexPageTableRow(self.Datasource.ColDefs))
        rows.extend(self.Datasource.Rows[irow:])
        self.Datasource.Rows=rows
        self.RefreshWindow()


    def OnPopupRenameCol(self, event):       
        self._dataGrid.OnPopupRenameCol(event) # Pass event to WxDataGrid to handle

        # Now we check the column header to see if it is one of the standard header. If so, we use the std definition for that header
        # (We have to do this here because WxDataGrid doesn't know about header semantics.)
        icol=self._dataGrid.clickedColumn
        cd=self.Datasource.ColDefs[icol]
        if cd.Name in gStdColHeaders:
            self.Datasource.ColDefs[icol]=gStdColHeaders[cd.Name]
        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()


    # Merge a PDF into a previously non-PDF line
    def OnPopupMergeRows(self, event):
        self.wxGrid.SaveEditControlValue()
        top, _, bottom, _=self._dataGrid.SelectionBoundingBox()
        # Merge is only active when we have two rows selected and exactly one of this is a pdf.
        # We merge the filename from the PDF row into the data of the non-PDF row.  If there is a PDF column, we merge that, too.
        # Then we delete the (former) PDF column
        pdfline=top
        oldline=bottom
        if self.Datasource.Rows[bottom][0].lower().endswith(".pdf"):
            pdfline=bottom
            oldline=top
        self.Datasource.Rows[oldline][0]=self.Datasource.Rows[pdfline][0]
        pdfcol=self.Datasource.ColHeaderIndex("PDF")
        if pdfcol != -1:
            self.Datasource.Rows[oldline][pdfcol]="PDF"
        self._dataGrid.DeleteRows(pdfline)
        self._dataGrid.Grid.ClearSelection()
        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()


    # Replace the URL of a PDF or HTML page in the 1st column with a PDF
    def OnPopupReplace(self, event):
        # Call the File Open dialog to select a single PDF file
        with wx.FileDialog(self,
                           message="Select one PDF file to replace existing target",
                           defaultDir=self.PDFSourcePath,
                           wildcard="PDF files (*.pdf)|*.pdf",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.STAY_ON_TOP) as dlg:

            if dlg.ShowModal() != wx.ID_OK:
                return  # Quit unless OK was pressed.

            filepath=dlg.Paths

        if len(filepath) != 1:     # Should never happen as there's no way to return from dlg w/o selecting pdfs or hitting cancel.  But just in case...
            return

        irow=self._dataGrid.clickedRow
        oldfile=self.Datasource.Rows[irow][0]
        newfilepath, newfilename=os.path.split(filepath[0])
        self.Datasource.Rows[irow][0]=newfilename
        self.deltaTracker.Replace(oldSourceFilename=oldfile, newfilepathname=filepath[0], serverDirName=self.ServerDir, row=self.Datasource.Rows[irow])
        self.FillInPDFColumn()
        self.RefreshWindow()

        event.Skip()


    # Rename the PDF on the server. This does not change its name locally
    def OnPopupRenamePDF(self, event):
        oldname=self.Datasource.Rows[self._dataGrid.clickedRow][0]
        dlg=wx.TextEntryDialog(self, 'Enter the newname of the pdf: ', 'Rename a PS+DF on the server', value=oldname)
        #dlg.SetValue("Turn a cell into a link")
        if dlg.ShowModal() != wx.ID_OK:
            event.Skip()
            return
        newname=dlg.GetValue()
        dlg.Destroy()

        if newname == "" or newname == oldname:
            event.Skip()
            return

        irow=self._dataGrid.clickedRow
        self.Datasource.Rows[irow][0]=newname
        self.RefreshWindow()
        self.deltaTracker.Rename(oldname, newname, serverDirName=self.ServerDir, row=self.Datasource.Rows[irow])

        event.Skip()


    # Clear links in the selected row
    def OnPopupClearAllLinks(self, event):
        row=self.Datasource.Rows[self._dataGrid.clickedRow]
        for i, col in enumerate(row.Cells):
            before, link, target, aft=FindLinkInString(col)
            if link != "":
                row[i]=before+target+aft

        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()


    # Add a link to the selected cell
    def OnPopupInsertLinkLine(self, event):
        irow=self._dataGrid.clickedRow
        icol=self._dataGrid.clickedColumn
        if irow == -1 or icol == -1:
            event.Skip()
            return

        if irow > self.Datasource.NumRows:
            self._dataGrid.ExpandDataSourceToInclude(irow, 0)   # If we're inserting past the end of the datasource, insert empty rows as necessary to fill in between
        self._dataGrid.InsertEmptyRows(irow, 1)     # Insert the new empty row

        row=self.Datasource.Rows[irow]
        val=row[icol]
        # Create text input
        dlg=wx.TextEntryDialog(self, 'Enter the URL to be used (just the URL, no HTML): ', 'Turn cell text into a hyperlink')
        #dlg.SetValue("Turn a cell into a link")
        if dlg.ShowModal() != wx.ID_OK:
            event.Skip()
            return
        ret=dlg.GetValue()
        dlg.Destroy()

        if ret == "":
            event.Skip()
            return

        row[icol]=ret
        self._dataGrid.Grid.SetCellSize(irow, 0, 1, self._dataGrid.NumCols)
        for icol in range(self._dataGrid.NumCols):
            self._dataGrid.AllowCellEdit(irow, icol)
        self.Datasource.Rows[irow].IsLinkRow=True
        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()


    # A sort function which treats the input text (if it can) as NNNaaa where NNN is sorted as an integer and aaa is sorted alphabetically.  Decimal point ends NNN.
    @staticmethod
    def PseudonumericSort(x: str) -> float:
        if IsInt(x):
            return float(int(x))
        m=re.match(r"([0-9]+)\.?(.*)$", x)
        if m is None:
            return 0
        # Turn the trailing junk into something like a number.  The trailing junk will be things like ".1" or "A"
        junk=m.groups()[1]
        dec=0
        pos=1
        for j in junk:
            dec+=ord(j)/(256**pos)      # Convert the trailing junk into ascii numbers and divide by 256 to create a float which sorts in the same order
            pos+=1
        return int(m.groups()[0])+dec


    # Sort a mailing column.  They will typically be an APA name follwoed by a mailing number, sometimes sollowed by a letter
    @staticmethod
    def MailingSort(h: str) -> int:
        if len(h.strip()) == 0:
            return 0
        # First, strip the surrounding HTML
        h=RemoveHyperlink(h)
        m=re.match(r"^[ a-zA-Z0-9-]* ([0-9]+)[a-zA-Z]?\s*$", h)
        if m:
            return Int0(m.groups()[0])
        return 0


    def OnPopupSortOnSelectedColumn(self, event):       
        self.wxGrid.SaveEditControlValue()
        # We already know that only a single column is selected because that's the only time this menu item is enabled and can be called
        col=self._dataGrid.clickedColumn
        # If the column consists on thong but empty cells and numbers, we do a special numerical sort.
        testIsInt=all([(x[col] == "" or IsInt(x[col])) for x in self.Datasource.Rows])
        if testIsInt:
            self.Datasource.Rows.sort(key=lambda x: Int0(x[col]))
        else:
            testIsMonth=all([(x[col] == "" or MonthNameToInt(x[col])) is not None for x in self.Datasource.Rows])
            if testIsMonth:
                self.Datasource.Rows.sort(key=lambda x: ZeroIfNone(MonthNameToInt(x[col])))
            else:
                if self.Datasource.ColHeaders[col].lower() == "mailing":
                    self.Datasource.Rows.sort(key=lambda x: self.MailingSort(x[col]))
                else:
                    testIsSortaNum=self.Datasource.ColDefs[col].Name == "WholeNum" or self.Datasource.ColDefs[col].Name == "Whole" or \
                                   self.Datasource.ColDefs[col].Name == "Vol" or self.Datasource.ColDefs[col].Name == "Volume" or \
                                   self.Datasource.ColDefs[col].Name == "Num" or self.Datasource.ColDefs[col].Name == "Number"
                    if testIsSortaNum:
                        self.Datasource.Rows.sort(key=lambda x: self.PseudonumericSort(x[col]))
                    else:
                        self.Datasource.Rows.sort(key=lambda x:x[col])
        self.RefreshWindow()


    # ------------------
    def OnPopupInsertText(self, event):
        irow=self._dataGrid.clickedRow
        if irow > self.Datasource.NumRows:
            self._dataGrid.ExpandDataSourceToInclude(irow, 0)   # If we're inserting past the end of the datasource, insert empty rows as necessary to fill in between
        self._dataGrid.InsertEmptyRows(irow, 1)     # Insert the new empty row
        self.Datasource.Rows[irow].IsTextRow=True
        self._dataGrid.Grid.SetCellSize(irow, 0, 1, self._dataGrid.NumCols)
        for icol in range(self._dataGrid.NumCols):
            self._dataGrid.AllowCellEdit(irow, icol)
        self.RefreshWindow()


    def OnPopupInsertColLeft(self, event):       
        self._dataGrid.OnPopupInsertColLeft(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupInsertColRight(self, event):       
        self._dataGrid.OnPopupInsertColRight(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupExtractScanner(self, event):       
        self.wxGrid.SaveEditControlValue()
        self.ExtractScannerFromNotes()
        self.RefreshWindow()

    def OnPopupTidyUpColumns(self, event):       
        self.wxGrid.SaveEditControlValue()
        self.ExtractApaMailings()
        self.FillInPDFColumn()
        self.FillInPagesColumn()
        self.StandardizeColumns()
        self.RefreshWindow()


    def OnPopupAllowEditing(self, event):       
        self.wxGrid.SaveEditControlValue()
        self._dataGrid.AllowCellEdit(self._dataGrid.clickedRow, self._dataGrid.clickedColumn)
        self.RefreshWindow()


    # Run through the rows and columns and look at the Notes column  If an APA mailing note is present,
    # move it to a "Mailing" column (which may need to be created).  Remove the text from the Notes column.
    # Find the Notes column. If there is none, we're done.
    def ExtractApaMailings(self):       
        if "Notes" not in self._Datasource.ColHeaders:
            return
        notescol=self._Datasource.ColHeaders.index("Notes")

        # Collect the mailing into in this until later when we have a chance to put it in its own column
        # Only if we determine that a mailing exists will be try to add it to the mailings column (perhaps creating it, also.)
        mailings=[""]*len(self._Datasource.Rows)

        # Look through the rows and extract mailing info, if any
        # We're looking for things like [for/in] <apa> nnn. Parhaps, more than one separated by commas or ampersands
        apas: list[str]=Settings().Get("apas")
        if len(apas) == 0:
            LogError(f"ExtractApaMailings() could not read apa list from settings.txt")
        # Now turn this into a pattern
        patapas="|".join(apas)
        for i, row in enumerate(self._Datasource.Rows):
            note=row[notescol]
            #note=RemoveHyperlink(note)  # Some apa mailing entries are hyperlinked and those hyperlinks are a nuisance.  WQe now add them automatically, so they can go for now.

            # Run through the list of APAs, looking for in turn the apa name followed by a number and maybe a letter
            # Sometimes the apa name will be preceded by "in" or "for"
            # Sometimes the actual apa mailing name will be the text of a hyperlink
            mailingPat=fr"({patapas})\s+([0-9]+[a-zA-Z]?)"  # Matches APA 123X

            # First look for a mailing name inside a hyperlink and, if found, remove the hyperlink
            note=RemoveHyperlinkContainingPattern(note, mailingPat, repeat=True, flags=re.IGNORECASE)

            while True:
                # With any interfering hyperlink removed, look for the mailing spec
                pat=rf"(?:for|in|)?\s*{mailingPat}\s*(pm|postmailing)?(,|&)?"
                m=re.search(pat, note, flags=re.IGNORECASE)
                if m is None:
                    break

                # We found a mailing.  Add it to the temporary list of mailings and remove it from the mailings column
                if mailings[i]:
                    mailings[i]+=" & "
                mailings[i]+=m.groups()[0]+" "+m.groups()[1]
                if m.groups()[2]:
                    mailings[i]+= " postmailing"
                note=re.sub(pat, "", note, count=1, flags=re.IGNORECASE).strip()  # Remove the matched text

            if mailings[i]:     # We don't update the notes column unless we found a mailing
                row[notescol]=note


        # If any mailings were found, we need to put them into their new column (and maybe create the new column as well.)
        if any([m for m in mailings]):

            # Append a mailing column if needed
            if "Mailing" not in self._Datasource.ColHeaders:
                self._Datasource.InsertColumnHeader(-1, gStdColHeaders["Mailing"])
                # Append an empty cell to each row
                for row in self._Datasource.Rows:
                    row.Extend([""])

            # And move the mailing info
            mailcol=self._Datasource.ColHeaders.index("Mailing")
            for i, row in enumerate(self._Datasource.Rows):
                if mailings[i]:
                    if row[mailcol]:
                        row[mailcol]+=" & "
                    row[mailcol]+=mailings[i]


    # Run through the rows and columns and look at the Notes column  If an editor note is present,
    # move it to a "Editors" column (which may need to be created).  Remove the text from the Notes column.
    def OnPopupExtractEditor(self, event):  
        self.wxGrid.SaveEditControlValue()

        # Find the Notes column. If there is none, we're done.
        if "Notes" not in self._Datasource.ColHeaders:
            return
        notescol=self._Datasource.ColHeaders.index("Notes")

        # Look through the rows and extract mailing info, if any
        # We're looking for things like Edited by/Editor nnn
        editors=[""]*len(self._Datasource.Rows)  # Collect the editor into in this until later when we have a chance to put it in its own column
        for i, row in enumerate(self._Datasource.Rows):
            # Look for 'edited by xxx' or 'edited: xxx'
            # xxx can be one of three patterns:
            #       Aaaa Bbbb
            #       Aaaa B Cccc
            #       Aaaa B. Cccc
            pat=r"[eE](ditor|dited by|d\.?):?\s*([A-Z][a-zA-Z]+\s+[A-Z]?[.]?\s*[A-Z][a-zA-Z]+)\s*"
            m=re.search(pat, row[notescol])
            if m is not None:
                # We found an editor.
                eds=m.groups()[1]
                locs=m.regs[0]
                r=row[notescol]
                r=r.replace(r[locs[0]:locs[1]], "")
                if len(r) > 0:
                    pat=r"\s*(and|&|,)\s*([A-Z][a-zA-Z]+\s+[A-Z]?[.]?\s*[A-Z][a-zA-Z]+)\s*"
                    r=r[locs[0]:]   # Want to search for co-editors only following the 1st editor which we just excised
                    m=re.search(pat, r)
                    if m is not None:
                        eds+=" & "+m.groups()[1]
                        locs=m.regs[0]
                        r=r.replace(r[locs[0]:locs[1]], "")

                editors[i]=eds
                row[notescol]=r

                row[notescol]=re.sub(pat, "", row[notescol]).strip()


        # If any editors were found, we need to put them into their new column (and maybe create the new column as well.)
        if any([m for m in editors]):

            # Append an editor column if needed
            if "Editor" not in self._Datasource.ColHeaders:
                self._Datasource.InsertColumnHeader(-1, gStdColHeaders["Editor"])
                # Append an empty cell to each row
                for row in self._Datasource.Rows:
                    row.Extend([""])

            # And move the editor info
            edcol=self._Datasource.ColHeaders.index("Editor")
            for i, row in enumerate(self._Datasource.Rows):
                if editors[i]:
                    if row[edcol]:
                        row[edcol]+=" & "
                    row[edcol]+=editors[i]

        self.RefreshWindow()


    def OnPopupParseDates( self, event ):
        self.wxGrid.SaveEditControlValue()

        dateCol=self._dataGrid.clickedColumn
        if "date" not in self.Datasource.ColDefs[dateCol].Preferred.lower():
            return

        yearcol=self.Datasource.ColHeaderIndex("Year")
        if yearcol == -1:
            self.Datasource.InsertColumn2(dateCol+1, "Year")
        daycol=self.Datasource.ColHeaderIndex("Day")
        if daycol == -1:
            self.Datasource.InsertColumn2(dateCol+1, "Day")
        monthcol=self.Datasource.ColHeaderIndex("Month")
        if monthcol == -1:
            self.Datasource.InsertColumn2(dateCol+1, "Month")
        # The columns to the left of Date might have been shuffled, so get them again
        yearcol=self.Datasource.ColHeaderIndex("Year")
        daycol=self.Datasource.ColHeaderIndex("Day")
        monthcol=self.Datasource.ColHeaderIndex("Month")
        
        # Now extract the date
        for i, row in enumerate(self._Datasource.Rows):
            date=row[dateCol]
            if len(date) == 0:
                continue  # Skip empty dates

            dt=FanzineDate().Match(date)
            if dt.IsEmpty():
                continue

            # Don't overwrite existing m/d/y data
            if len(row[daycol]) == 0:
                row[daycol]=str(dt.Day)
            if len(row[monthcol]) == 0:
                row[monthcol]=dt.MonthName
            if len(row[yearcol]) == 0:
                row[yearcol]=str(dt.Year)

        self.RefreshWindow()


    # If there is an editors column and if editors have been specific for the whole run, replace all blank cells in the editors column with the series' editors.
    def OnPopupPropagateEditor(self, event):  
        self.wxGrid.SaveEditControlValue()

        if len(self.Editors) == 0:
            return

        editorscol=FindIndexOfStringInList(self._Datasource.ColHeaders, ["Editor", "Editors"])
        if editorscol is None:
            return

        # Go through the cells in the Editors column and fill in any which are empty with the contents of tEditors
        for row in self._Datasource.Rows:
            if row[editorscol] is None or len(row[editorscol].strip()) == 0:
                eds=self.Editors
                if "\n" in eds:
                    eds=" / ".join([x.strip() for x in eds.split("\n")])
                row[editorscol]=eds

        self.RefreshWindow()


#*******************************************
# Take a list of column names and generate a list of ColDefs
def ColNamesToColDefs(headers: list[str]) -> ColDefinitionsList:
    colDefs: ColDefinitionsList=ColDefinitionsList([])
    for header in headers:
        # First cannonicize the header
        if header.lower() == "issue":
            header="Display Text"   # Display text is unique to Fanzines Index Page??
        elif header.lower() == "title":
            header="Display Text"   # But a few pages usne "Title"
        else:
            header=CanonicizeColumnHeaders(header)

        if header in gStdColHeaders:
            scd=gStdColHeaders[gStdColHeaders.index(header)]
        else:
            header=header.strip("(").strip(")")     # Remove existing parens so when we add one back. there's just one.
            scd=ColDefinition(f"({header})", Type="str", Width=75)  # The default when it's unrecognizable

        colDefs.append(scd)
    return colDefs


#####################################################################################################
#####################################################################################################

class FanzineIndexPage(GridDataSource):
    def __init__(self):
        GridDataSource.__init__(self)
        self._colDefs: ColDefinitionsList=ColDefinitionsList([])
        self._fanzineList: list[FanzineIndexPageTableRow]=[]
        self._gridDataRowClass=FanzineIndexPageTableRow
        self._specialTextColor: Color|None=None
        self.TopComments: str=""
        self.Locale: list[str]=[]
        self._name: FanzineNames=FanzineNames()
        self._clubname: str=""
        self._betterScanNeeded: bool=False
        self._Editors: str=""
        self._version: str=""
        self.Dates: str=""
        self.Significance: str="Unclassified"
        self.FanzineType: str=""
        self.Complete=False     # Is this fanzine series complete?
        self.Credits=""         # Who is to be credited for this affair?
        self.Updated: ClassicFanzinesDate=ClassicFanzinesDate("Long, long ago")


    def Signature(self) -> int:        
        s=0
        if self._colDefs is not None:
            s+=self._colDefs.Signature()
        s+=hash(f"{self._name};{self.TopComments.strip()};{' '.join(self.Locale).strip()}")
        s+=hash(f"{self.TopComments.strip()};{' '.join(self.Locale).strip()};{self.Significance}")
        s+=hash(f"{self.Name.MainName};{self.Editors};{self.Dates};{self.FanzineType};{self.Clubname};{self.Credits}")
        s+=sum([x.Signature()*(i+1) for i, x in enumerate(self._fanzineList)])
        s+=hash(self._specialTextColor)
        return s


    # Inherited from GridDataSource
    @property
    def Rows(self) -> list[FanzineIndexPageTableRow]:        
        return self._fanzineList
    @Rows.setter
    def Rows(self, rows: list) -> None:        
        self._fanzineList=rows


    @property
    def NumRows(self) -> int:        
        return len(self._fanzineList)

    def __getitem__(self, index: int) -> FanzineIndexPageTableRow:        
        return self.Rows[index]

    def __setitem__(self, index: int, val: FanzineIndexPageTableRow) -> None:        
        self._fanzineList[index]=val


    @property
    def SpecialTextColor(self) -> Color|None:        
        return self._specialTextColor
    @SpecialTextColor.setter
    def SpecialTextColor(self, val: Color|None) -> None:        
        self._specialTextColor=val


    def __str__(self) -> str:
        return str(self.Updated)


    def CanAddColumns(self) -> bool:        
        return True


    def InsertEmptyRows(self, insertat: int, num: int=1) -> None:        
        for i in range(num):
            ftr=FanzineIndexPageTableRow(self._colDefs)
            self._fanzineList.insert(insertat+i, ftr)


    @property
    def Name(self) -> FanzineNames:
        return self._name
    @Name.setter
    def Name(self, val: FanzineNames) -> None:
        assert isinstance(val, FanzineNames)
        self._name=val

    @property
    def Clubname(self) -> str:
        if self.FanzineType.lower() == "clubzine":
            return self._clubname.strip()
        return ""
    @Clubname.setter
    def Clubname(self, val: str) -> None:
        # We want to ignore leading spaces or a leading hyphen
        val=val.strip()
        if len(val) > 0 and val[0] == "-":
            val=val[1:].strip()
        self._clubname=val


    @property
    def TextAndHrefCols(self) -> (int, int):
        return self._colDefs.index("Display Text"), self._colDefs.index("Link")


    @staticmethod
    def SelectNonNavigableStrings(soupstuff) -> list:        
        return [x for x in soupstuff if not isinstance(x, bs4.element.NavigableString)]


    # Download a fanzine index page fanac.org/fanzines/URL and fill in the class
    def GetFanzineIndexPage(self, url: str) -> bool:
        fanzineServerDir=""
        testRootDirectory=Settings().Get("Test Root directory")
        html=None
        if Settings().Get("Test mode", "False") == "True":
            if testRootDirectory != "":
                # If there is a test directory, try loading from there, first
                fanzineServerDir=f"/{testRootDirectory}/{url}"
                html=FTP().GetFileAsString(fanzineServerDir, "index.html", TestLoad=True)
        if html is None:
            # If we're not in test mode or if that failed (or there wasn't one) load from the default server directory
            fanzineServerDir=f"/{Settings().Get("Root directory")}/{url}"
            html=FTP().GetFileAsString(fanzineServerDir, "index.html")
        if html is None:
            LogError(f"Unable to download 'index.html' from '{url}' because {FTP().LastMessage}")
            return False

        # Remove the &amp;amp;amp;amp;amp;... that has crept in to some pages.
        while "&amp;amp;" in html:
            html=html.replace("amp;amp;", "amp;")
            Log(f"redundant 'amp;'s removed from {url}")

        # This is the tag that marks a new-style page and its version.
        # e.g., <!-- fanac fanzine index page V1.0-->
        # Version " " -- old (Jack) pages
        # Version "2" -- The first batch of FanzinesEditor pages
        # Version "2.1" -- starting mid-December 2024, pages where we have guaranteed that ampersands in URLs are correctly written
        self._version=ExtractInvisibleTextInsideFanacComment(html, "fanzine index page V").strip()
        if self._version == "":
            success=self.GetFanzineIndexPageOld(html)
        else:
            success=self.GetFanzineIndexPageNew(html, fanzineServerDir)

        if not success:
            return False

        # Get the signatures of each line to later use to see if the line has been updated.
        for row in self.Rows:
            row._Signature=row.Signature()

        return True

    # Dunno why this keeps croping up in some of the html...
    def RemoveA0C2Crap(self, s: str) -> str:
        x=s.replace("\xc2\xa0", " ").replace(u"\u00A0", " ")
        x=x.replace("0xa0", " ").replace("0xc2", " ")
        return x


    def GetFanzineIndexPageOld(self, html: str) -> bool:  
        soup=BeautifulSoup(html, 'html.parser')
        body=soup.findAll("body")
        bodytext=str(body)

        bodytext=self.RemoveA0C2Crap(bodytext)
        _, bodytext=SearchAndReplace(r"(<script>.+?</script>)", bodytext, "", ignorenewlines=True)


        tables=body[0].findAll("table")
        top=tables[0]
        theTable=tables[2]
        #bottom=tables[3]

        locale=""
        localeStuff=body[0].findAll("fanac-type")
        if len(localeStuff) > 0:
            localeStuff=str(localeStuff[0])
            _, localeStuff=SearchAndReplace(r"(</?fanac-type>)", localeStuff, "")
            _, locale=SearchAndReplace(r"(</?h2/?>)", localeStuff, "")

        # Check for the (now obsolete) Alphabetize Individually flag
        # If we find it set, we set the type choice to "Collection".  We never write out an FIP with the Alphabetize Individually flag set
        m=re.search(r"<!-- Fanac-keywords: (.*?) -->", str(body[0]), flags=re.DOTALL|re.MULTILINE|re.IGNORECASE)
        if m is not None:
            if len(m.groups()[0]) > 10:     # Arbitrary, since the keyword should be "Alphabetize Individually", but has been added by hand so might be mosta nyhting
                self.FanzineType="Collection"

        name=FanzineNames()
        editors=""
        dates=""
        fanzinetype=""
        # Extract the fanzine Name, Editors, Dates and Type
        if len(top.findAll("td")) > 1:
            topmatter=top.findAll("td")[1]
            # This looks like:
            # '<td border="none" class="fmz"><h1 class="sansserif">Apollo<br/><h2>Joe Hensley <br/> Lionel Innman<br/><h2>1943 - 1946<br/><br/>Genzine</h2></h2></h1></td>'
            # Split it first by <h[12].
            topmattersplit=re.split(r"</?h[12]/?>", str(topmatter))
            name.IntepretOldHeader(topmattersplit[0])

            for i, stuff in enumerate(topmattersplit):
                stuff=re.sub(r"</?br/?>", "\n", stuff)
                _, stuff=SearchAndReplace(r"(<.*?>)", stuff, "")        # Replace all HTML <xxxx> with empty string
                topmattersplit[i]=stuff
            topmattersplit=[x.replace("\n\n", "\n").removesuffix("\n") for x in topmattersplit if x != ""]
            if len(topmattersplit) == 0:
                LogError(f"Malformed top matter on page.")
            # Editors can be separated by "\n", "'", ";" and other stuff.  Split on spans of these characters
            editors=SplitListOfNamesOnPattern(topmattersplit[1], r", and |,|/|;|and |&|\n|<br>")
            dates, fanzinetype=topmattersplit[2].replace("&nbsp;", " ").replace("&NBSP;", " ").split("\n")

        # We look for a block of free-form comments.  It should lie between the <fanac-type>...</fanac-type> block and the start of the rows table.
        loc=html.find("</fanac-type>")
        if loc != -1:
            locend=html.find("<TABLE", loc)
            if locend != -1:
                s=html[loc+len("</fanac-type>"):locend]
                s=s.replace("<p>", "\n")
                s=RemoveAllHTMLLikeTags(s)
                self.TopComments=s.strip()

        # Now interpret the table to generate the column headers and data rows
        theRows=theTable.findAll("tr")
        headers: list[str]=[]
        if len(theRows) > 0:
            row0=theRows[0].findAll("th")
            if len(row0) > 0:
                headers=[RemoveAllHTMLLikeTags(str(x)) for x in row0]

        # And construct the grid
        # Column #1 is always a link to the fanzine, and we split this into two parts, the URL and the display text
        # We prepend a URL column before the Issue column. This will hold the filename which is the URL for the link
        self._colDefs=ColDefinitionsList([ColDefinition("Link", 100, "url", IsEditable.Maybe)])
        self._colDefs.append(ColNamesToColDefs(headers))

        # Get the column number of the Mailing column, if any.
        iMailingCol=None
        if "Mailing" in self._colDefs:
            iMailingCol=self._colDefs.index("Mailing")

        if len(theRows) > 1:
            for thisrow in theRows[1:]:

                cols=thisrow.findAll("td")

                # We treat column 0 specially, extracting its hyperref and turning it into two
                cols0=str(cols[0])
                cols0=self.RemoveA0C2Crap(cols0)
                _, url, text, _=FindLinkInString(cols0)
                url=HtmlEscapesToUnicode(url, isURL=True)
                if url == "" and text == "":
                    cols0=RemoveAllHTMLLikeTags(cols0)
                    row=["", cols0]
                else:
                    row=[url, text]

                cols=[RegularizeBRTags(str(x)) for x in cols[1:]]   # Turn all <br/> and </br> to <br>
                cols=[RemoveTopLevelHTMLTags(x, LeaveLinks=True) for x in cols]     # Remove non-link HTML
                cols=[x if x.strip().lower() != "<br>" else "" for x in cols]   # Remove all <br> (old FIPs sometimes has this in blank cells)

                # We treat the Mailing column (if present) specially by removing the hyperlink to the issue -- it will be returned when it is loaded back to the server.
                if iMailingCol is not None:
                    cols[iMailingCol-2]=RemoveAllHTMLLikeTags(cols[iMailingCol-2])      # The -2 is because the first two columns were handled separately, above.

                row.extend(cols)
                self.Rows.append(FanzineIndexPageTableRow(self._colDefs, row) )

        credits=""
        loc=bodytext.rfind("</table>")
        if loc >= 0:
            lasttext=bodytext[loc+len("</table>"):]
            lasttext=re.split(r"</?br/?", lasttext)
            lasttext=[RemoveAllHTMLLikeTags(x) for x in lasttext]
            lasttext=[x.replace(r"/n", "").replace("\n", "") for x in lasttext]
            lasttext=[x for x in lasttext if len(x) > 0]
            if len(lasttext) == 2:
                credits=lasttext[0]

        # Some old FIPs have a Date column: Try to split it up into Day+Month+Year
        datecol=max(self.ColHeaderIndex("Date"), self.ColHeaderIndex("(Date)"))
        if datecol != -1:
            # OK, first try to add Day, Month and Year cols
            if self.ColHeaderIndex("Year") == -1:
                self.InsertColumn2(datecol, gStdColHeaders["Year"])
            if self.ColHeaderIndex("Day") == -1:
                self.InsertColumn2(datecol, gStdColHeaders["Day"])
            if self.ColHeaderIndex("Month") == -1:
                self.InsertColumn2(datecol, gStdColHeaders["Month"])

            datecol=max(self.ColHeaderIndex("Date"), self.ColHeaderIndex("(Date)"))     # The inserts will shuffle columns, so need to re-evaluate this
            daycol=self.ColHeaderIndex("Day")
            monthcol=self.ColHeaderIndex("Month")
            yearcol=self.ColHeaderIndex("Year")
            for row in self.Rows:
                if row[datecol] != "":
                    date=FanzineDate().Match(row[datecol])
                    d=InterpretRelativeWords(date.DayText)
                    if d is None:
                        d=date.DayText
                    row[daycol]=d
                    row[monthcol]=date.MonthText
                    row[yearcol]=date.YearText
                    i=0




        Log(f"GetFanzinePageOld():")
        Log(f"     {credits=}")
        Log(f"     {dates=}")
        Log(f"     {editors=}")
        Log(f"     {fanzinetype=}")
        Log(f"     {locale=}")
        Log(f"     {name.MainName=}")
        self.Credits=credits
        self.Dates=dates
        self.Editors=editors
        self.FanzineType=fanzinetype
        self.Locale=locale
        self._name=name

        return True


    @property
    def Editors(self):
        return self._Editors
    @Editors.setter
    def Editors(self, val: str|list):
        self._Editors=val
        # v=val
        # if isinstance(val, list):
        #     if len(val) == 1:
        #         v=val[0]
        #     else:
        #         v=", ".join(val)
        # elif "<br>" in val:
        #     v="\n".join([x.strip() for x in val.split(", ")])
        #
        # self._Editors=v



    def GetFanzineIndexPageNew(self, html: str, fanzineServerDir: str) -> bool:

        def CleanUnicodeText(s: str) -> str:
            return HtmlEscapesToUnicode(RemoveFancyLink(s)).strip()

        html2=CleanUnicodeText(html)
        #html=RemoveFunnyWhitespace(html)

        html=self.RemoveA0C2Crap(html)

        # Update the version number
        html=InsertInvisibleTextInsideFanacComment(html, "fanzine index page V", "2.1")   # Version being written.  self._version is what was read.

        # f"{self.Name.MainName}<BR><H2>{self.Editors}<BR><H2>{self.Dates}<BR><BR>{self.FanzineType}"
        topstuff=ExtractHTMLUsingFanacStartEndCommentPair(html, "header")
        if topstuff == "":
            LogError(f"GetFanzineIndexPageNew() failed: ExtractHTMLUsingFanacComments('header')")
            return False

        self.Name.MainName=CleanUnicodeText(ExtractHTMLUsingFanacTagCommentPair(topstuff, "name"))
        other=ExtractHTMLUsingFanacTagCommentPair(topstuff, "other")
        other=[CleanUnicodeText(x) for x in [y for y in SplitOnSpansOfLineBreaks(other)]]
        self.Name.Othernames=other
        self.Editors=[CleanUnicodeText(x) for x in RemoveHyperlink(ExtractHTMLUsingFanacTagCommentPair(topstuff, "eds"), repeat=True).split("<br>")]
        self.Dates=ExtractHTMLUsingFanacTagCommentPair(topstuff, "dates")
        self.Complete="complete" in ExtractHTMLUsingFanacTagCommentPair(topstuff, "complete").lower()
        self.FanzineType=ExtractHTMLUsingFanacTagCommentPair(topstuff, "type")
        self.Clubname=CleanUnicodeText(ExtractHTMLUsingFanacTagCommentPair(topstuff, "club"))

        self.Significance=ExtractInvisibleTextInsideFanacComment(html, "sig")

        # f"<H2>{TurnPythonListIntoWordList(self.Locale)}</H2>"
        self.Locale=CleanUnicodeText(ExtractHTMLUsingFanacTagCommentPair(html, "loc"))
        if self.Locale == "":
            Log(f"GetFanzineIndexPageNew(): ExtractHTMLUsingFanacComments('Locale') -- No locale found")
        # Remove the <h2>s that tend to decorate it

        comments=ExtractHTMLUsingFanacStartEndCommentPair(html, "topcomments")
        if comments is not None:
            self.TopComments=comments.replace("<br>", "\n")

        # Now interpret the table to generate the column headers and data rows
        headers=ExtractHTMLUsingFanacStartEndCommentPair(html, "table-headers")
        if headers == "":
            LogError(f"GetFanzineIndexPageNew() failed: ExtractHTMLUsingFanacComments('table-headers')")
            return False
        # Interpret the column headers
        # f "\n<TR>\n<TH>{self.ColHeaders[1]}</TH>\n"...insert+=f"<TH>{header}</TH>\n" (repeats)..."</TR>\n"
        headers=re.findall(r"<TH>(.+?)</TH>", headers, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE)
        self._colDefs=ColNamesToColDefs(headers)
        # In a normal row, column #1 is always a link to the fanzine, and so for every row, we split this into two parts,
        # the URL and the display text.
        # We prepend a URL column before the Issue column. This will hold the filename which is the URL for the link
        self._colDefs=ColDefinitionsList([ColDefinition("Link", 100, "url", IsEditable.Maybe)])+self._colDefs

        self.Created=ClassicFanzinesDate(ExtractInvisibleTextInsideFanacComment(html, "created"))
        self.Updated=ClassicFanzinesDate(ExtractHTMLUsingFanacTagCommentPair(html, "updated"))

        # There is an issue with V2 pages in which the code for the '&' in "Laurel & Hardy" in a URL was mis-handled.
        # If this page began as a V2 page, we'll need to look carefully at the filenames on the site and adjust the URLs in the rows to match.
        urlsOnServer: list[str]=[]
        if self._version == "2":
            urlsOnServer=FTP().Nlst(fanzineServerDir)

        # Now the rows
        rows=ExtractHTMLUsingFanacStartEndCommentPair(html, "table-rows")
        rows=re.findall(r"<TR>(.+?)</TR>", rows, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE)
        if rows == "":
            LogError(f"GetFanzineIndexPageNew() failed: ExtractHTMLUsingFanacComments('table-rows')")
            return False
        # Interpret the rows
        for row in rows:

            # First look for a link row
            # This starts with colspan= and is followed by <a href="col 0">col 1</a></TD>
            m=re.match(r'<TD colspan=\"[0-9]+\">(<a href=\"(.*?)">(.*?)</a>)</TD>', row, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE)
            if m is not None:
                fipr=FanzineIndexPageTableRow(self._colDefs)
                fipr.Cells[0]=m.groups()[1]
                fipr.Cells[1]=m.groups()[2]
                fipr.IsLinkRow=True
                self.Rows.append(fipr)
                continue

            # Next look for a row which is a pure text row
            # We detect the colspan= which merges all the row's cells into one, and since it isn't a link row, it's a text row
            m=re.match(r'<TD colspan=\"[0-9]+\">(.*?)</TD>', row, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE)
            if m is not None:
                fipr=FanzineIndexPageTableRow(self._colDefs)
                contents=StripSpecificTag(m.groups()[0], "b")
                contents=ConvertHTMLEscapes(contents)
                fipr.Cells[0]=contents

                fipr.IsTextRow=True
                self.Rows.append(fipr)
                continue

            # OK, it's a regular row.

            # The final "column" is actually a comment containing an updated datetime for the row. (It really isn't a table column at all.)
            # It may or may not exist.  If it exists, save it for later use.
            updated=""
            m=re.search(".*(<!-- Up: [0-9 -]*-->)", row)
            if m is not None:
                updated=m.groups()[0]

            rowsfound=re.findall(r"<TD(:?.*?)>(.*?)</TD>", row, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE)
            cols=[x[1] for x in rowsfound]

            # We treat the web page's column 0 specially, extracting its hyperref and display name and showing them as two column in FanzinesEditor
            # The first col is complicated, because it needs to have URLs which match the actual filename on the server. This is only an issue the first time we write a V2.1 or later FIP.
            # Expand the first col in the FIP into two columns for display
            cols0=str(cols[0])
            _, url, text, _=FindLinkInString(cols0)

            # UGLY! Kludge!
            # Edie requests that links to gostak.org.uk be treated specially and have a hard-wored http:
            if "gostak.org.uk" in url:
                url="http:"+url

            # There are at least a few pages which have "&amp;nbsp;" in text -- this should be displayed as "&nbsp;"
            text=text.replace("&amp;nbsp;", "&nbsp;")
            if self._version == "2":
                url=HtmlEscapesToUnicode(url, isURL=True).replace("&amp;", "&")
            else:
                url=HtmlEscapesToUnicode(url, isURL=True)
            if url == "" and text == "":
                cols=["", cols0]+cols[1:]
            else:
                cols=[url, text]+cols[1:]

            if cols is not None:
                row=[RemoveAllHTMLLikeTags(str(x)) for x in cols]
                fipr=FanzineIndexPageTableRow(self._colDefs, row)
            else:
                fipr=FanzineIndexPageTableRow(self._colDefs)
                fipr.IsTextRow=True

            fipr._UpdatedComment=updated
            self.Rows.append(fipr)

        self.Credits=ExtractHTMLUsingFanacStartEndCommentPair(html, "scan").strip()

        # Log(f"GetFanzinePageNew():")
        # Log(f"     {self.Credits=}")
        # Log(f"     {self.Dates=}")
        # Log(f"     {self.Editors=}")
        # Log(f"     {self.FanzineType=}")
        # Log(f"     {self.Clubname=}")
        # Log(f"     {self.Locale=}")
        # Log(f"     {self.Name.MainName=}")

        return True


    # Turn any mailing info into hyperlinks to the mailing on fanac.org
    def ProcessAPALinks(self, cell: str) -> str:
        if len(cell) == 0:
            return ""

        mailings=cell.replace(",", "&").replace(";", "&").split("&")     # It may be of the form 'FAPA 103 PM, OMPA 32 & SAPS 76A'
        out=[]
        for mailing in mailings:
            mailing=mailing.strip()
            if len(mailing) == 0:
                continue
            # Split mailing titles like FAPA 103A into an apa name and the mailing number (which may have trailing characters '30A')
            m=re.match(r"([a-zA-Z'1-9_\- ]*)\s+([0-9]+[a-zA-Z]*)\s*(pm|postmailing)?$", mailing, flags=re.IGNORECASE)
            if m is not None:
                apa=m.groups()[0]
                number=m.groups()[1]
                pm=m.groups()[2]
                if pm:
                    pm=" "+pm
                else:
                    pm=""
                out.append(f'<a href="https://fanac.org/fanzines/APA_Mailings/{apa}/{number}.html">{apa} {number}</a>{pm}')
        return ", ".join(out)


    # Using the fanzine index page template, create a page and upload it.
    # This puts a Version 2.1 page
    def PutFanzineIndexPage(self, root: str, url: str) -> bool:        

        # Get the Fanzine Index Page template
        if not os.path.exists("Template - Fanzine Index Page.html"):
            LogError(f"PutFanzineIndexPage() can't find ';'Template - Fanzine Index Page.html' at {os.path.curdir}")
            return False
        with open("Template - Fanzine Index Page.html") as f:
            output=f.read()

        # Insert the <head> matter: <meta name="description"...> and <title>
        edlist=", ".join([x for x in self.Editors.split("\n")])
        names=[self.Name.MainName]
        names.extend(self.Name.Othernames)
        namelist=", ".join(names)
        content=f'{namelist}, {edlist}, {self.Dates.strip()}, {self.FanzineType.strip()}'
        if self.Clubname != "":
            content+=f", {self.Clubname}"
        meta=f'meta name="description" content="{content}"'
        output=FindAndReplaceSingleBracketedText(output, "meta name=", f"<{UnicodeToHtmlEscapes(meta)}>")

        output, rslt=FindAndReplaceBracketedText(output, "title", f"<title>{UnicodeToHtmlEscapes(self.Name.MainName)}</title>", caseInsensitive=True)

        output=InsertBetweenHTMLComments(output, "name", UnicodeToHtmlEscapes(self.Name.MainName))
        output=InsertBetweenHTMLComments(output, "other", self.Name.OthernamesAsHTML)
        output=InsertBetweenHTMLComments(output, "eds", "<br>".join([SpecialNameFormatToHtmlFancylink(UnicodeToHtmlEscapes(x.strip())) for x in self.Editors.split("\n")]))
        output=InsertBetweenHTMLComments(output, "dates", UnicodeToHtmlEscapes(self.Dates.strip()))
        output=InsertBetweenHTMLComments(output, "complete", "(Complete)" if self.Complete else "")
        output=InsertBetweenHTMLComments(output, "type", self.FanzineType.strip())
        output=InsertBetweenHTMLComments(output, "club", f" - {UnicodeToHtmlEscapes(self.Clubname)}" if self.Clubname != "" else "")
        output=InsertBetweenHTMLComments(output, "loc", TurnPythonListIntoWordList(self.Locale))

        output=InsertInvisibleTextInsideFanacComment(output, "sig", self.Significance)

        insert=UnicodeToHtmlEscapes(self.TopComments).replace("\n", "<br>")
        insert=self.TopComments.replace("\n", "<br>")
        temp=InsertHTMLUsingFanacStartEndCommentPair(output, "topcomments", insert.strip())
        if temp == "":
            LogError(f"PutFanzineIndexPage({url}) failed: InsertHTMLUsingFanacComments('topcomments')")
            return False
        output=temp

        keywords=""     # Not currently being used
        temp=InsertInvisibleTextInsideFanacComment(output, "keywords", keywords)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url}) failed: InsertInvisibleTextUsingFanacComments('fanac-keywords')")
            return False
        output=temp

        # Now interpret the table to generate the column headers and data rows
        # The 1st col is the URL, and it gets mixed with the 2nd to form an Href.
        insert="\n<TR>\n"
        if len(self.ColHeaders) < 2:
            LogError(f"PutFanzineIndexPage({url}) failed: {len(self.ColHeaders)=}")
            return False
        insert+=f"<TH>Issue</TH>\n"
        for header in self.ColHeaders[2:]:
            insert+=f"<TH>{header}</TH>\n"
        insert+="</TR>\n"
        temp=InsertHTMLUsingFanacStartEndCommentPair(output, "table-headers", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url}) failed: InsertHTMLUsingFanacComments('table-headers')")
            return False
        output=temp

        # Now the rows:
        # Accumulate the table lines in <insert>
        insert=""
        for row in self.Rows:

            if row.IsEmptyRow:
                insert+=f"\n<TR>"
                for i in range(self.NumCols-1):
                    insert+=f"<TD>&nbsp;</TD>\n"
                insert+=f"</TR>\n"
                continue

            if row.IsTextRow:
                # If the row is an anchor for an in-page href, we need to detect it and handle it correctly.
                contents=row.Cells[0]
                if not re.match(r"<a name=.*>", contents, flags=re.IGNORECASE):
                    contents=UnicodeToHtmlEscapes(contents)
                insert+=f'\n<TR><TD colspan="{self.NumCols}"><b>{contents}</b></TD></TR>'
                continue

            if row.IsLinkRow:
                insert+=(fr'\n<TR><TD colspan="{self.NumCols}"><a href="{row.Cells[0]}">{UnicodeToHtmlEscapes(row.Cells[1])}</a></TD></TR>')
                continue

            # OK, it's an ordinary row
            # Unfortunately, some legacy ordinary rows don't have a file to point to -- they're just place holders.
            # We must handle them specially.
            # Format cols 0 and 1 into a single column for the website
            insert+=f"\n<TR>"
            href=row.Cells[0].replace("#", "%23").replace("&", "%26").strip()
            if href != "":
                insert+=f'\n<TD><a href="{href}">{row.Cells[1]}</A></TD>\n'
            else:
                insert+=f'\n<TD>{row.Cells[1]}</TD>\n'
            # And now the rest
            for i, cell in enumerate(row.Cells[2:]):
                if self.ColHeaders[i+2].lower() == "mailing":
                    insert+=f"<TD CLASS='left'>{self.ProcessAPALinks(cell)}</TD>\n"
                else:
                    insert+=f"<TD CLASS='left'>{cell}</TD>\n"

            # Record the update date of this line
            if row._Signature != row.Signature():
                # We have to update the updated comment before appending it
                row._UpdatedComment=f"<!-- Up: {datetime.now():%Y-%m-%d}-->"
            insert+=row._UpdatedComment+"\n"
            insert+=f"</TR>\n"

        # Insert the accumulated table lines into the template
        temp=InsertHTMLUsingFanacStartEndCommentPair(output, "table-rows", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url}) failed: InsertHTMLUsingFanacComments('table-rows')")
            return False
        output=temp

        temp=InsertHTMLUsingFanacStartEndCommentPair(output, "scan", UnicodeToHtmlEscapes(self.Credits))
        # Different test because we don't always have a credit in the file.
        if len(temp) > 0:
            output=temp

        # Update the updated text at the bottom of the page
        temp=InsertHTMLUsingFanacStartEndCommentPair(output, "updated", f"Updated {ClassicFanzinesDate().Now()}")
        if temp == "":
            LogError(f"Could not InsertUsingFanacComments('updated')")
        else:
            output=temp

        ret=FTP().PutFileAsString(f"/{root}/{url}", "index.html", output, create=True)
        if not ret:
            LogError(f"Could not FTP().PutFileAsString FIP '/{root}/{url}/index.html' because {FTP().LastMessage}")

        return ret



def SetPDFMetadata(pdfPathFilename: str, row: FanzineIndexPageTableRow, colNames: ColDefinitionsList, editors: str="", mainName: str="", country: str="") -> str:

    try:
        writer=PdfWriter(clone_from=pdfPathFilename)
    except FileNotFoundError:
        wx.MessageBox(f"Unable to open file {pdfPathFilename}")
        LogError((f"SetPDFMetadata: Unable to open file {pdfPathFilename}"))
        return ""

    # Title, issue, date, editors, country code, apa
    metadata={"/Title": row.Cells[colNames.index("Display Text")], "/Author": editors.replace("<br>", ", ")}
    if len(editors) > 0:
        metadata["/Author"]=editors

    keywords=f"{mainName}, "
    if "Year" in colNames:
        keywords+=f", {row.Cells[colNames.index('Year')]}"
    if "Mailing" in colNames:
        keywords+=f", {row.Cells[colNames.index('Mailing')]}"
    if len(country) > 0:
        keywords+=f", {country}"
    metadata["/Keywords"]=keywords

    # Add the metadata.
    try:
        writer.add_metadata(metadata)
    except:
        LogError(f"SetPDFMetadata().writer.add_metadata(metadata) with file {pdfPathFilename} threw an exception: Ignored")

    # Use the temporary directory
    tmpdirname=gettempdir()
    Log(f"Temporary directory: {tmpdirname}")
    filename=os.path.basename(pdfPathFilename)
    Log(f"{filename=}")
    newfilepath=os.path.join(tmpdirname, filename)
    Log(f"{newfilepath=}")

    with open(newfilepath, 'wb') as fp:
        writer.write(fp)
    return newfilepath