from __future__ import annotations

from typing import Optional
import os
import wx
import wx.grid
import re
from datetime import datetime
from string import capwords
from math import floor, ceil

from bs4 import BeautifulSoup
import bs4

from GenGUIClass import FanzineIndexPageEditGen
from ClassicFanzinesLine import ClassicFanzinesLine, ClassicFanzinesDate
from DeltaTracker import DeltaTracker

from FTP import FTP

from WxDataGrid import DataGrid, Color, GridDataSource, ColDefinition, ColDefinitionsList, GridDataRowClass, IsEditable
from WxHelpers import OnCloseHandling, ProgressMsg, ProgressMessage, ProcessChar
from WxHelpers import ModalDialogManager
from HelpersPackage import IsInt, Int0, ZeroIfNone
from HelpersPackage import  FindLinkInString, FindIndexOfStringInList, FindIndexOfStringInList2
from HelpersPackage import RemoveHyperlink, RemoveHyperlinkContainingPattern, CanonicizeColumnHeaders, RemoveArticles
from HelpersPackage import SearchAndReplace, RemoveAllHTMLLikeTags, TurnPythonListIntoWordList
from HelpersPackage import InsertInvisibleTextUsingFanacComments, InsertHTMLUsingFanacComments, ExtractHTMLUsingFanacComments, ExtractInvisibleTextUsingFanacComments
from HelpersPackage import  InsertInvisibleTextInsideFanacComment, ExtractInvisibleTextInsideFanacComment
from PDFHelpers import GetPdfPageCount
from Log import Log, LogError
from Settings import Settings
from FanzineIssueSpecPackage import MonthNameToInt

# Create default column headers
gStdColHeaders: ColDefinitionsList=ColDefinitionsList([
    ColDefinition("Filename", Type="str"),
    ColDefinition("Issue", Type="required str"),
    ColDefinition("Title", Type="str", preferred="Issue"),
    ColDefinition("Whole", Type="int", Width=75),
    ColDefinition("WholeNum", Type="int", Width=75, preferred="Whole"),
    ColDefinition("Vol", Type="int", Width=50),
    ColDefinition("Volume", Type="int", Width=50, preferred="Vol"),
    ColDefinition("Num", Type="int", Width=50),
    ColDefinition("Number", Type="int", Width=50, preferred="Num"),
    ColDefinition("Month", Type="str", Width=75),
    ColDefinition("Day", Type="int", Width=50),
    ColDefinition("Year", Type="int", Width=50),
    ColDefinition("Pages", Type="int", Width=50),
    ColDefinition("PDF", Type="str", Width=50),
    ColDefinition("Notes", Type="str", Width=120),
    ColDefinition("Scanned", Type="str", Width=100),
    ColDefinition("Country", Type="str", Width=50),
    ColDefinition("Editor", Type="str", Width=75),
    ColDefinition("Author", Type="str", Width=75),
    ColDefinition("Mailing", Type="str", Width=75),
    ColDefinition("Repro", Type="str", Width=75)
])


class FanzineIndexPageWindow(FanzineIndexPageEditGen):
    def __init__(self, parent, serverDir: str= ""):
        FanzineIndexPageEditGen.__init__(self, parent)

        self.failure=True

        # IsNewDirectory True means this FIP is newly created and has not yet been uploaded.
        # We can tell because an existing fanzine must be opened by supplying a server directory, while for a new fanzine, the server directory must be the empty string
        # Some fields are editable only for new fanzines (which will be in new server directories, allowing some things to be set for the first time.).
        self.IsNewDirectory=False
        if serverDir == "":
            self.IsNewDirectory=True
        self.serverDir=serverDir

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

        self._dataGrid: DataGrid=DataGrid(self.wxGrid)
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
                gStdColHeaders["Issue"],
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
            # This is not a new directory
            # Load the fanzine index page
            with ProgressMsg(parent, f"Downloading Fanzine Index Page: {serverDir}"):
                self.failure=False
                if not self.Datasource.GetFanzineIndexPage(serverDir):
                    self.failure=True
                    return

            # Add the various values into the dialog
            self.tCredits.SetValue(self.Datasource.Credits)
            self.tDates.SetValue(self.Datasource.Dates)
            self.tEditors.SetValue(self.Datasource.Editors)
            self.tFanzineName.SetValue(self.Datasource.FanzineName)
            if self.Datasource.FanzineType in self.tFanzineType.Items:
                self.tFanzineType.SetSelection(self.tFanzineType.Items.index(self.Datasource.FanzineType))
            self.tLocaleText.SetValue(self.Datasource.Locale)
            self.tTopComments.SetValue(self.Datasource.TopComments)

            self.cbComplete.SetValue(self.Datasource.Complete)
            self.cbAlphabetizeIndividually.SetValue(self.Datasource.AlphabetizeIndividually)

            # The server directory is not editable when it already exists.
            # If the input parameter serverDirectory is empty, then we're creating a new fanzine entry and the serverDirectory can and must be edited.
            if self.serverDir != "":
                self.tServerDirectory.SetValue(self.serverDir)
                self.tServerDirectory.Disable()

            self.localDir=Settings("ServerToLocal").Get(self.serverDir)
            if self.localDir is not None:
                self.tLocalDirectory.SetValue(self.localDir)
                self.tLocalDirectory.Disable()

            # Now load the fanzine issue data
            self._dataGrid.HideRowLabels()

            self._dataGrid.NumCols=self.Datasource.NumCols
            if self._dataGrid.NumRows > self.Datasource.NumRows:
                self._dataGrid.DeleteRows(self.Datasource.NumRows, self._dataGrid.NumRows-self.Datasource.NumRows)
            else:
                self._dataGrid.AppendRows(self.Datasource.NumRows)

        # Read in the table of local directory to server directory equivalences
        with open("ServerToLocal Conversion.txt", "r") as f:
            l2sLines=f.readlines()
        self.serverNameList: list[str]=[]
        self.localNameList: list[str]=[]
        for line in l2sLines:
            line=line.split()
            if len(line) == 2:
                self.localNameList.append(line[0])
                self.serverNameList.append(line[1])

        # Try to fill in the local directory
        if self.tServerDirectory.GetValue() in self.serverNameList:
            self.tLocalDirectory.SetValue(self.localNameList[self.serverNameList.index(self.tServerDirectory.GetValue())])


        self._dataGrid.RefreshWxGridFromDatasource()
        self.MarkAsSaved()
        self.RefreshWindow()
        self.failure=False



    @property
    def Datasource(self) -> FanzineIndexPage:       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        return self._Datasource
    @Datasource.setter
    def Datasource(self, val: FanzineIndexPage):
        self._Datasource=val
        self._dataGrid.Datasource=val


    # Look at information available and color buttons and fields accordingly.
    def ColorAndEnableFields(self):                      # FanzineIndexPageWindow(FanzineIndexPageEditGen)

        # Some things are turned on for both editing an old FIP and creating a new one
        self.tEditors.SetEditable(True)
        self.tDates.SetEditable(True)
        self.tFanzineType.Enabled=True
        self.tTopComments.SetEditable(True)
        self.tLocaleText.SetEditable(True)
        self.cbComplete.Enabled=True
        self.cbAlphabetizeIndividually.Enabled=True
        self.wxGrid.Enabled=True

        # A few are enabled only when creating a new one (which lasts onbly until it is uploaded -- then it's an old one)
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



    #------------------
    # An override of DataGrids's method ColorCellsByValue() for columns 0 and 1 only
    def ColorCells01ByValue(self, icol: int, irow: int):            # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        if icol != 0 and icol != 1:
            return
        if icol < 0 or icol >= self.Datasource.NumCols:
            return
        if irow < 0 or irow >= self.Datasource.NumRows:
            return

        return



    def OnClose(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        if not self.OKToClose(event):
            return

        # Save the window's position
        pos=self.GetPosition()
        Settings("FanzinesEditor positions.json").Put("Index Page Window Position", (pos.x, pos.y))
        size=self.GetSize()
        Settings("FanzinesEditor positions.json").Put("Index Page Window Size", (size.width, size.height))

        self.EndModal(wx.OK)



    # The user has requested that the dialog be closed or wiped and reloaded.
    # Check to see if it has unsaved information.
    # If it does, ask the user if he wants to save it first.
    def OKToClose(self, event) -> bool:             # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        if not self.NeedsSaving():
            return True

        if not OnCloseHandling(event, self.NeedsSaving(), "The changes have not been uploaded and will be lost if you exit. Quit anyway?"):
            self.MarkAsSaved()  # The contents have been declared doomed, so mark it as saved so as not to trigger any more queries.
            return True

        return False


    def OnAddNewIssues(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)

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

        # We have a list of file names and need to add them to the fanzine index page
        # Start by removing any already-existing empty trailing rows from the datasource
        while self.Datasource.Rows:
            last=self.Datasource.Rows.pop()
            if any([cell != "" for cell in last.Cells]):
                self.Datasource.Rows.append(last)
                break

        # Sort the new files by name and add them to the rows at the bottom
        files.sort()
        newrows=self.Datasource.AppendEmptyRows(len(files))
        for i, file in enumerate(files):
            newrows[i].FileSourcePath=files[i]
            newrows[i][0]=os.path.basename(files[i])


        # Add a PDF column (if needed) and fill in the PDF column and page counts
        self.FillInPDFColumn()
        self.FillInPagesColumn()

        # And add these files to the changelist
        for file in files:
            self.deltaTracker.Add(file)

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
    def FillInPDFColumn(self) -> None:              # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        iPdf=self.AddOrDeletePDFColumnIfNeeded()
        if iPdf != -1:
            for i, row in enumerate(self.Datasource.Rows):
                filename=row[0]
                if filename.lower().endswith(".pdf"):
                    row[iPdf]="PDF"


    #--------------------------
    # Check the rows to see if any of the files are a pdf
    # If a pdf is found possibly add a PDF column and fill the PDF column in for those rows.
    def FillInPagesColumn(self) -> None:                # FanzineIndexPageWindow(FanzineIndexPageEditGen)
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
    def AddOrDeletePDFColumnIfNeeded(self) -> int:              # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        # Are any of the files PDFs?
        noPDFs=not any([row[0].lower().endswith(".pdf") for row in self.Datasource.Rows])
        allPDFs=all([row[0].lower().endswith(".pdf") for row in self.Datasource.Rows])
        ipdfcol=self.Datasource.ColHeaderIndex("pdf")

        # We need do nothing in two cases: There are no PDFs or everything is a PDF and there is no PDF column
        # Then return -1
        if allPDFs and ipdfcol == -1:
            return -1
        if noPDFs:
            return -1

        # If they are all PDFs and there is a PDF column, it is redundant and should be removed
        if allPDFs and ipdfcol != -1:
            self.Datasource.DeleteColumn(ipdfcol)
            return -1

        # OK, there are *some* PDFs.

        # If there is a PDF column, we must move it to the right
        if ipdfcol == self.Datasource.NumCols-1:
            # We have a PDF column and it is on the right.  All's well. Just return its index.
            return ipdfcol

        # Is there no PDF column?
        if ipdfcol == -1:
            # Add one on the right and return its index
            self.Datasource.InsertColumn(self.Datasource.NumCols, ColDefinition("PDF"))
            return self.Datasource.NumCols-1

        # So we have one, but it is in the wrong place: Move it to the end
        self.Datasource.MoveColumns(self.Datasource.ColHeaderIndex("pdf"), 1, self.Datasource.NumCols-1)
        return self.Datasource.NumCols-1


    #------------------
    # The only columns *always* present are the Issue name/link, Year, Pages and Notes columns.
    # Other columns will be deleted if they are completely empty and there is more than one row defined.
    # The Mailing column (if any) will be automatically moved to the left of the Notes column.
    def StandardizeColumns(self) -> None:               # FanzineIndexPageWindow(FanzineIndexPageEditGen)

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


    # ------------------
    # Initialize an existing, initializedm main window to empty
    # This also initiazes the datasource
    def ClearMainWindow(self):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)

        # Create an empty datasource
        self.Datasource._fanzineList=[]

        # Update the dialog's grid from the data
        self._dataGrid.RefreshWxGridFromDatasource(RetainSelection=False)

        # Fill in the dialog's upper stuff
        self.tFanzineName.SetValue("")
        self.tTopComments.SetValue("")
        self.tEditors.SetValue("")
        self.tDates.SetValue("")
        self.tFanzineType.SetSelection(0)
        self.tLocaleText.SetValue("")
        self.tCredits.SetValue("")
        self.cbComplete.SetValue(False)
        self.cbAlphabetizeIndividually.SetValue(False)

        self.Datasource.Credits=Settings().Get("Scanning credits default", default="")

        # Set the signature to the current (empty) state so any change will trigger a request to save on exit
        self.MarkAsSaved()


    #------------------
    # Upload the current FanzineIndexPage (including any added fanzines) to the server
    def OnUpload(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        with ModalDialogManager(ProgressMessage, self) as progressMessage:
            progressMessage.Show(f"Uploading Fanzine Index Page: {self.serverDir}")
            Log(f"Uploading Fanzine Index Page: {self.serverDir}")
            self.failure=False

            # Make a dated backup copy of the existing page
            ProgressMessage(self).UpdateMessage(f"Backing up FanzineIndexPage")
            ret=FTP().CopyAndRenameFile(f"/Fanzines-test/{self.serverDir}", "index.html",
                                    f"/Fanzines-test/{self.serverDir}", f"index - {datetime.now()}.html")
            if not ret:
                Log(f"Could not make a backup copy: Fanzines-test/{self.serverDir}/index - {datetime.now()}.html")
                self.failure=True
                return

            self.serverDir=self.tServerDirectory.GetValue()

            # Now execute the delta list on the files.
            failure=False
            for delta in self.deltaTracker.Deltas:
                match delta.Verb:
                    case "add":
                        # Copy file to server, possibly renaming it
                        path=delta.SourcePath
                        filename=delta.SourceFilename
                        pathfilename=os.path.join(path, filename)
                        serverpathfile=f"/Fanzines-test/{self.serverDir}/{delta.SourceFilename}"
                        if delta.NewSourceFilename != "":
                            serverpathfile=f"/Fanzines-test/{self.serverDir}/{delta.NewSourceFilename}"
                        progressMessage.Show(f"Uploading {delta.SourceFilename} as {delta.NewSourceFilename}")
                        if not FTP().PutFile(pathfilename, serverpathfile):
                            dlg=wx.MessageDialog(self, f"Y+Unable to upload {pathfilename}?", "Continue?", wx.YES_NO|wx.ICON_QUESTION)
                            result=dlg.ShowModal()
                            dlg.Destroy()
                            if result != wx.ID_YES:
                                failure=True
                                break
                        continue

                    case "delete":
                        # Delete a file on the server
                        servername=delta.SourceFilename
                        serverpathfile=f"/Fanzines-test/{self.serverDir}/{servername}"
                        progressMessage.Show(f"Deleting {serverpathfile} from server")
                        if not FTP().DeleteFile(serverpathfile):
                            dlg=wx.MessageDialog(self, f"Y+Unable to delete {serverpathfile}?", "Continue?", wx.YES_NO|wx.ICON_QUESTION)
                            result=dlg.ShowModal()
                            dlg.Destroy()
                            if result != wx.ID_YES:
                                failure=True
                                break
                        continue
                    case "rename":
                        # Rename file on the server
                        assert delta.NewSourceFilename != ""
                        oldserverpathfile=f"/Fanzines-test/{self.serverDir}/{delta.SourceFilename}"
                        newserverpathfile=f"/Fanzines-test/{self.serverDir}/{delta.NewSourceFilename}"
                        progressMessage.Show(f"Renaming {oldserverpathfile} as {newserverpathfile}")
                        if not FTP().Rename(oldserverpathfile, newserverpathfile):
                            dlg=wx.MessageDialog(self, f"Y+Unable to rename {oldserverpathfile} to {newserverpathfile}", "Continue?", wx.YES_NO|wx.ICON_QUESTION)
                            result=dlg.ShowModal()
                            dlg.Destroy()
                            if result != wx.ID_YES:
                                failure=True
                                break
                        continue


            # If this is a new fanzine, it needs to be in a new directory.  Check it.
            if self.IsNewDirectory:
                path=f"/Fanzines-test/{self.serverDir}"
                if FTP().PathExists(path):
                    wx.MessageBox(f"'Directory {path}' already exists.  Please change the server directory name.", parent=self)
                    self.failure=True
                    return

            # Check the dates to make sure that the dated issues all fall into the date range given for the fanzine
            # Date range sgould be of the form yyyy-yyyy with question marks abounding
            dates=self.tDates.GetValue()
            # Unless there is exactly one hyphen in the range, we can't do comparisons
            if dates.count("-") == 1:
                # Remove question marks, as they tell us nothing.  Then split
                dates=dates.replace("?", "")
                date1, date2=dates.split("-")
                # The dates should be of one of these forms:
                #       yyyy, <empty>, 1950s, Ppresent
                #       empty is interpreted as 1920 or 2100, depending on which side of the hyphen it's on
                #       present is interpreted as, well, now.
                #       something like 1950s is interpreted as the start or end of the decade depending on which side of the hyphen it's on
                d1=Int0(date1)
                d2=Int0(date2)
                if date2.lower() == "present":
                    d2=datetime.now().year+1
                if date1[-1].lower() == "s":
                    # This ends in "s", it must either be something like 1950s or garbage
                    d1=Int0(date1[:-1])
                    if d1 > 1900:
                        d1=10*floor(d1/10)
                # Also check date 2
                if date2[-1].lower() == "s":
                    # This ends in "s", it must either be something like 1950s or garbage
                    d2=Int0(date2[:-1])
                    if d2 > 1900:
                        d2=10*ceil(d2/10)
                # OK, we now change zero dates into 1900 and 2200, respectively so that zero matches everything
                if d1 == 0:
                    d1=1900
                if d2 == 0:
                    d2=2200

                # Now check this against all the years in the rows.
                icol=self.Datasource.ColHeaderIndex("year")
                failed=False
                if icol != -1:
                    for row in self.Datasource.Rows:
                        year=row[icol]
                        # Remove question marks and interpret the rest
                        year=year.replace("?", "")
                        year=Int0(year)
                        if year > 0:        # Ignore missing years
                            if year < d1 or year > d2:
                                failed=True
                if failed:
                    wx.MessageBox("Warning: One or more of the years in the table are outside the date range given fore this fanzine.", parent=self)

            # Put the FanzineIndexPage on the server as an HTML file
            if not self.Datasource.PutFanzineIndexPage(self.serverDir):
                self.failure=True
                Log("Failed\n")
                return
            for row in self.Datasource.Rows:
                if row.FileSourcePath != "":
                    ProgressMessage(self).UpdateMessage(f"Uploading file: {row.FileSourcePath}")
                    Log(f"Uploading file: {row.FileSourcePath}")
                    if not FTP().PutFile(row.FileSourcePath, f"/Fanzines-test/{self.serverDir}/{row.Cells[0]}"):
                        Log("Failed\n")
                        self.failure=True
                        return
                    row.FileSourcePath=""

            Log("All uploads succeeded.")

            # Save the fanzine's uploaded values to return to the main fanzines page.
            cfl=ClassicFanzinesLine()
            cfl.Issues=self.Datasource.NumRows
            cfl.Editors=self.tEditors.GetValue().replace("\n", "<br>")
            cfl.ServerDir=self.tServerDirectory.GetValue()

            cfl.DisplayName=self.tFanzineName.GetValue()
            cfl.OtherNames="??"
            cfl.Dates=self.tDates.GetValue()
            cfl.Type=self.tFanzineType.Items[self.tFanzineType.GetSelection()]
            cfl.Complete=self.cbComplete.GetValue()
            cfl.Updated=datetime.now()
            if cfl.Created == ClassicFanzinesDate("1900-01-01"):
                cfl.Created=datetime.now()
            cfl.TopComments=self.tTopComments.GetValue()
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

            self.UpdateEnabledStatus()





    def UpdateNeedsSavingFlag(self):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        s="Editing "+self.serverDir
        if self.NeedsSaving():
            s=s+" *"        # Append a change marker if needed
        self.SetTitle(s)


    def UpdateEnabledStatus(self):
        # The server directory can be edited iff this is a new directory
        self.tServerDirectory.Enabled=self.IsNewDirectory

        def IsEmpty(s: str) -> bool:
            return s.strip() == ""

        # The Upload button is enabled iff certain text boxes have content  and there's at least one fanzine
        enable=True
        if IsEmpty(self.tServerDirectory.GetValue()) or IsEmpty(self.tFanzineName.GetValue()) or IsEmpty(self.tLocalDirectory.GetValue()):
            enable=False
        if len(self.Datasource.Rows) == 0:
            enable=False
        self.bUpload.Enabled=enable

        # The local directory text box is editable in a new directory, but not in an existing one
        self.tLocalDirectory.Enabled=len(self.tLocalDirectory.GetValue()) == 0 or self.IsNewDirectory


    def RefreshWindow(self, DontRefreshGrid: bool=False)-> None:       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.UpdateNeedsSavingFlag()
        self.UpdateEnabledStatus()

        if not DontRefreshGrid:
            self._dataGrid.RefreshWxGridFromDatasource()
        self.ColorAndEnableFields()


    # ----------------------------------------------
    # Used to determine if anything has been updated
    def Signature(self) -> int:       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        return self.Datasource.Signature()


    def MarkAsSaved(self):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self._signature=self.Signature()
        self.UpdateNeedsSavingFlag()


    def NeedsSaving(self):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        return self._signature != self.Signature()


    # This method updates the local directory name by computing it from the fanzine name.  It only applies when creating a new fanzine index page
    def OnFanzineNameChar(self, event):
        # Now do routine character handling
        event.Skip()

        # Requests from Edie:
        # Suppress leading articles, eg The or A
        # Remove non-letter characters, eg apostrophes or commas
        # Local directories all in caps Server directories with first letters of words capitalized
        # Spaces around dashes suppressed (eg fanzine title of: Bangsund - Other Publications)
        # Ability to manually add text to the server and local directories (eg fanzine title: Cinder ; server directory Cinder-Williams)
        # Ability to manually delete text for the server and local directories (eg fanzine title: Prolapse / Relapse ; server directory Prolapse)

        # Pick up the current value of the fanzine name field
        fname, cursorloc=ProcessChar(self.tFanzineName.GetValue(), event.GetKeyCode(), self.tFanzineName.GetInsertionPoint())

        Log(f"OnFanzineNameChar: Local directory name updated to '{fname}'")

        self.UpdateServerAndLocalDirNames(fname)


    def UpdateServerAndLocalDirNames(self, fname):
        # If this is a new fanzine, and if the user has not overridden the default server directory name by editing it himself, update the Server Directory name
        Log(f"OnFanzineNameChar: {self.tServerDirectory.Enabled=}    {self._manualEditOfServerDirectoryNameBegun=}'")
        if self.tServerDirectory.Enabled and not self._manualEditOfServerDirectoryNameBegun:
            # Strip leading "The", etc
            sname=RemoveArticles(fname).strip()
            if len(sname) > 0:
                if len(sname) == 1:
                    sname=sname.upper()
                else:
                    sname=sname[0].upper()+sname[1:].lower()
                    sname=re.sub("[^a-zA-Z0-9-]+", "_", sname)  # Replace all spans of not-listed chars with underscore
                    sname=sname.strip("_")  # Do not start or end names with underscores
                    sname=[capwords(x) for x in sname.split("_")]  # Split the name on underscores and capitolize all words

                    def capit(s: str):
                        lcwords=["And", "The", "A", "An", "With", "To", "From", "Over", "Of", "In", "Without"]  # Words which should be lower case if they are not the first word
                        if s in lcwords:
                            s=s.lower()
                        return s

                    sname=[capit(x) for x in sname]  # Swap special words back to lower case
                    sname="_".join(sname)
            self.tServerDirectory.SetValue(sname)
            Log(f"OnFanzineNameChar: Server directory name updated to '{sname}'")
        # If this is a new fanzine, and if the user has not overridden the default local directory name by editing it himself, update the Local Directory name
        Log(f"OnFanzineNameChar: {self.tLocalDirectory.Enabled=}    {self._manualEditOfLocalDirectoryNameBegun=}'")
        if self.tLocalDirectory.Enabled and not self._manualEditOfLocalDirectoryNameBegun:
            # Strip leading "The", etc
            lname=RemoveArticles(fname).strip()
            lname=re.sub("[^a-zA-Z0-9-]+", "_", lname)  # Replace all spans of not-listed chars with underscore
            lname=lname.strip("_")  # Do not start or end names with underscores
            lname=lname.upper()
            self.tLocalDirectory.SetValue(lname)
            Log(f"OnFanzineNameChar: Local directory name updated to '{lname}'")


    def OnFanzineNameText(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.Datasource.FanzineName=self.tFanzineName.GetValue()
        Log(f"OnFanzineNameText: Fanzine name updated to '{self.Datasource.FanzineName}'")
        self.UpdateServerAndLocalDirNames(self.Datasource.FanzineName)
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
        Log(f"OnServerDirectoryChar: updated to '{fname}'")
        return


    def OnLocalDirectoryChar( self, event ):
        Log(f"OnLocalDirectoryChar: triggered")
        if not self.IsNewDirectory:     # Only for new fanzines can the local directory name be updated
            return

        fname, cursorloc=ProcessChar(self.tLocalDirectory.GetValue(), event.GetKeyCode(), self.tLocalDirectory.GetInsertionPoint())
        self.tLocalDirectory.SetValue(fname)
        self.tLocalDirectory.SetInsertionPoint(cursorloc)

        self._manualEditOfLocalDirectoryNameBegun=True
        Log(f"OnLocalDirectoryChar: updated to '{fname}'")
        return


    def OnEditorsText(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.Datasource.Editors=self.tEditors.GetValue()
        self.RefreshWindow(DontRefreshGrid=True)


    def OnDatesText(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.Datasource.Dates=self.tDates.GetValue()
        self.RefreshWindow(DontRefreshGrid=True)


    def OnFanzineTypeSelect(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)

        self.Datasource.FanzineType=self.tFanzineType.GetItems()[self.tFanzineType.GetSelection()]
        self.RefreshWindow(DontRefreshGrid=True)

    #------------------
    def OnTopCommentsText(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        if self.Datasource.TopComments is not None and len(self.Datasource.TopComments) > 0:
            self.Datasource.TopComments=self.tTopComments.GetValue()
        else:
            self.Datasource.TopComments=self.tTopComments.GetValue().strip()

        self.RefreshWindow(DontRefreshGrid=True)

    # ------------------
    def OnCheckComplete(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.Datasource.Complete=self.cbComplete.GetValue()
        Log(f"OnCheckComplete(): {self.Datasource.Complete=} and {self.Datasource.AlphabetizeIndividually=}")
        self.RefreshWindow(DontRefreshGrid=True)

    # ------------------
    def OnCheckAlphabetizeIndividually(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.Datasource.AlphabetizeIndividually=self.cbAlphabetizeIndividually.GetValue()
        Log(f"OnCheckAlphabetizeIndividually(): {self.Datasource.Complete=} and {self.Datasource.AlphabetizeIndividually=}")
        self.RefreshWindow(DontRefreshGrid=True)
        # Don't need to refresh because nothing changed


    #------------------
    def OnLocaleText(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.Datasource.Locale=self.tLocaleText.GetValue().split("\n")
        self.RefreshWindow(DontRefreshGrid=True)

    #------------------
    def OnCreditsText(self, event):
        self.Datasource.Credits=self.tCredits.GetValue().strip()
        self.RefreshWindow(DontRefreshGrid=True)

    #-------------------
    def OnKeyDown(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self._dataGrid.OnKeyDown(event) # Pass event to WxDataGrid to handle
        self.UpdateNeedsSavingFlag()

    #-------------------
    def OnKeyUp(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self._dataGrid.OnKeyUp(event) # Pass event to WxDataGrid to handle

    #------------------
    def OnGridCellChanged(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        # If the change is to col 0 -- the URL -- then we need to queue a Delta so the change actually gets made. Save the old name.
        oldURL=""
        if event.GetCol() == 0:
            oldURL=self.Datasource.Rows[event.GetRow()][0]

        self._dataGrid.OnGridCellChanged(event)  # Pass event handling to WxDataGrid

        # If needed, queue the Delta
        if event.GetCol() == 0:
            self.deltaTracker.Rename(oldURL, self.Datasource.Rows[event.GetRow()][0])

        if event.GetCol() == 0:    # If the Filename changes, we may need to update the PDF and the Pages columns
            self.FillInPDFColumn()
            self.FillInPagesColumn()
        self.RefreshWindow()

    #------------------
    def OnGridCellRightClick(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        # Do generic RMB on grid processing
        self._dataGrid.OnGridCellRightClick(event, self.m_GridPopup)

        # Call the RMB handler
        self.RMBHandler(event, True)

    # ------------------
    def OnGridLabelLeftClick(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self._dataGrid.OnGridLabelLeftClick(event)

    #------------------
    def OnGridLabelRightClick(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        # Do generic RMB on grid processing
        self._dataGrid.OnGridCellRightClick(event, self.m_GridPopup)

        # Call the RMB handler
        self.RMBHandler(event, False)


    # RMB click handling for grid and grid label clicks
    def RMBHandler(self, event, isGridCellClick: bool):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)

        # Everything remains disabled when we're outside the defined columns
        if self._dataGrid.clickedColumn > self.Datasource.NumCols:    # Click is outside populated columns.
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
                    Enable("Merge Adjacent Rows")

        # If cell 0 is clicked on, and it contains the URL of a PDF or an HTML page, allow it to be replaced by a PDF.
        if self._dataGrid.clickedColumn == 0:
            irow=self._dataGrid.clickedRow
            if "pdf" in self.Datasource.Rows[irow][0].lower() or "html" in self.Datasource.Rows[irow][0].lower():
                Enable("Replace PDF")

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

        # If this is a cell in a column tagged as IsEditable=Maybe, enable allow editing
        if self.Datasource.ColDefs[self._dataGrid.clickedColumn].IsEditable == IsEditable.Maybe:
            Enable("Allow Editing")

        Enable("Tidy Up Columns")

        if self.Datasource.ColHeaders[self._dataGrid.clickedColumn] == "Editor" and self.tEditors.GetValue() is not None and len(self.tEditors.GetValue()) > 0:
            Enable("Propagate Editor")

        # Pop the menu up.
        self.PopupMenu(self.m_GridPopup)


    # ------------------
    # Extract 'scanned by' information from the Notes column, if any
    def ExtractScannerFromNotes(self):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)

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
            "[sS](can by|cans by|canned by|canned at|canning by) ([A-Z][a-z]+) ("   # A variation of "scanned by" followed by a first name;
            #   This all followed by one of these:
            "(?:Mc|Mac|O')[A-Z][a-z]+|"     # Celtic names
            "[A-Z]\.[A-Z][a-z]+|"   # Middle initial
            "[A-Z][a-z]+|" # This needs to go last because it will ignore characters after it finds a match (with "Sam McDonald" it matches "Sam Mc")
            "[0-9]+)"       # Boskone 23
        )
        pattern='[sS](?:can by|cans by|canned by|canned at|canning by) ([A-Z][a-z]+ (?:Mc|Mac|O\'\s?)?[A-Z][a-z]+|[A-Z]\\.[A-Z][a-z]+|[A-Z][a-z]+|[0-9]+)'

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


    def OnPopupCopy(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self._dataGrid.OnPopupCopy(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow(DontRefreshGrid=True)


    def OnPopupPaste(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self._dataGrid.OnPopupPaste(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()


    def OnPopupEraseSelection(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self._dataGrid.OnPopupEraseSelection(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()


    def OnPopupDelCol(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        if self.Datasource.Element.CanDeleteColumns:
            self._dataGrid.DeleteSelectedColumns() # Pass event to WxDataGrid to handle
        self.RefreshWindow()


    def OnPopupDelRow(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        # Add the deletions to the delta tracker
        top, _, bottom, _=self._dataGrid.SelectionBoundingBox()
        if top == -1 or bottom == -1:
            top=self._dataGrid.clickedRow
            bottom=self._dataGrid.clickedRow
        urlCol=self.Datasource.ColHeaderIndex("URL")
        assert urlCol != -1
        for irow in range(top, bottom+1):
            self.deltaTracker.Delete(self.Datasource.Rows[irow][urlCol])

        self._dataGrid.DeleteSelectedRows() # Pass event to WxDataGrid to handle
        self.RefreshWindow()


    def OnPopupInsertRow(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        irow=self._dataGrid.clickedRow
        # Insert an empty row just before the clicked row
        rows :[FanzineIndexPageTableRow]=[]
        if irow > 0:
            rows=self.Datasource.Rows[:irow]
        rows.append(FanzineIndexPageTableRow(self.Datasource.ColDefs))
        rows.extend(self.Datasource.Rows[irow:])
        self.Datasource.Rows=rows
        self.RefreshWindow()


    def OnPopupRenameCol(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self._dataGrid.OnPopupRenameCol(event) # Pass event to WxDataGrid to handle

        # Now we check the column header to see if it iss one of the standard header. If so, we use the std definition for that header
        # (We have to do this here because WxDataGrid doesn't know about header semantics.)
        icol=self._dataGrid.clickedColumn
        cd=self.Datasource.ColDefs[icol]
        if cd.Name in gStdColHeaders:
            self.Datasource.ColDefs[icol]=gStdColHeaders[cd.Name]
        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()


    # Merge a PDF into a previously non-PDF line
    def OnPopupMerge(self, event):
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

            newfile=dlg.GetFilenames()

        if len(newfile) != 1:     # Should never happen as there's no way to return from dlg w/o selecting pdfs or hitting cancel.  But just in case...
            return

        oldfile=self.Datasource.Rows[event.GetRow()][0]
        self.Datasource.Rows[event.GetRow()][0]=newfile[0]
        self.deltaTracker.Replace(oldfile, newfile[0])
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
    def OnPopupAddLink(self, event):
        if self._dataGrid.clickedRow == -1 or self._dataGrid.clickedColumn == -1:
            event.Skip()
            return

        row=self.Datasource.Rows[self._dataGrid.clickedRow]
        val=row[self._dataGrid.clickedColumn]
        # Create text input
        dlg=wx.TextEntryDialog(self, 'Turn cell text into a hyperlink', 'URL to be used: ')
        #dlg.SetValue("Turn a cell into a link")
        if dlg.ShowModal() != wx.ID_OK:
            event.Skip()
            return
        ret=dlg.GetValue()
        dlg.Destroy()

        if ret == "":
            event.Skip()
            return

        val=f'<a href="https:{ret}">{val}</a>'
        row[self._dataGrid.clickedColumn]=val
        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()


    # A sort function which treats the input text (if it can) as NNNaaa where NNN is sorted as an integer and aaa is sorted alphabetically.  Decimal point ends NNN.
    @staticmethod
    def PseudonumericSort(x: str) -> float:
        if IsInt(x):
            return float(int(x))
        m=re.match("([0-9]+)\.?(.*)$", x)
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
        m=re.match("^[ a-zA-Z0-9-]* ([0-9]+)[a-zA-Z]?\s*$", h)
        if m:
            return Int0(m.groups()[0])
        return 0


    def OnPopupSortOnSelectedColumn(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
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

    def OnPopupInsertColLeft(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self._dataGrid.OnPopupInsertColLeft(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupInsertColRight(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self._dataGrid.OnPopupInsertColRight(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupExtractScanner(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.wxGrid.SaveEditControlValue()
        self.ExtractScannerFromNotes()
        self.RefreshWindow()

    def OnPopupTidyUpColumns(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.wxGrid.SaveEditControlValue()
        self.ExtractApaMailings()
        self.FillInPDFColumn()
        self.FillInPagesColumn()
        self.StandardizeColumns()
        self.RefreshWindow()


    def OnPopupAllowEditing(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.wxGrid.SaveEditControlValue()
        self._dataGrid.AllowCellEdit(self._dataGrid.clickedRow, self._dataGrid.clickedColumn)
        self.RefreshWindow()


    # Run through the rows and columns and look at the Notes column  If an APA mailing note is present,
    # move it to a "Mailing" column (which may need to be created).  Remove the text from the Notes column.
    # Find the Notes column. If there is none, we're done.
    def ExtractApaMailings(self):       # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        if "Notes" not in self._Datasource.ColHeaders:
            return
        notescol=self._Datasource.ColHeaders.index("Notes")

        # Collect the mailing into in this until later when we have a chance to put it in its own column
        # Only if we determine that a mailing exists will be try to add it to the mailings column (perhaps creating it, also.)
        mailings=[""]*len(self._Datasource.Rows)

        # Look through the rows and extract mailing info, if any
        # We're looking for things like [for/in] <apa> nnn. Parhaps, more than one separated by commas or ampersands
        apas: list[str]=["FAPA", "SAPS", "OMPA", "ANZAPA", "VAPA", "FLAP", "FWD", "FIDO", "TAPS", "APA-F", "APA-L", "APA:NESFA", "WOOF", "SFPA"]
        # Now turn this into a pattern
        patapas="|".join(apas)
        for i, row in enumerate(self._Datasource.Rows):
            note=row[notescol]
            #note=RemoveHyperlink(note)  # Some apa mailing entries are hyperlinked and those hyperlinks are a nuisance.  WQe now add them automatically, so they can go for now.

            # Run through the list of APAs, looking for in turn the apa name followed by a number and maybe a letter
            # Sometimes the apa name will be preceded by "in" or "for"
            # Sometimes the actual apa mailing name will be the text of a hyperlink
            mailingPat=f"({patapas})\s+([0-9]+[a-zA-Z]?)"  # Matches APA 123X

            # First look for a mailing name inside a hyperlink and, if found, remove the hyperlink
            note=RemoveHyperlinkContainingPattern(note, mailingPat, repeat=True, flags=re.IGNORECASE)

            while True:
                # With any interfering hyperlink removed, look for the mailing spec
                pat=f"(?:for|in|)?\s*{mailingPat}\s*(pm|postmailing)?(,|&)?"
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
    def OnPopupExtractEditor(self, event):  # FanzineIndexPageWindow(FanzineIndexPageEditGen)
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
            pat="[eE](ditor|dited by|d\.?):?\s*([A-Z][a-zA-Z]+\s+[A-Z]?[.]?\s*[A-Z][a-zA-Z]+)\s*"
            m=re.search(pat, row[notescol])
            if m is not None:
                # We found an editor.
                eds=m.groups()[1]
                locs=m.regs[0]
                r=row[notescol]
                r=r.replace(r[locs[0]:locs[1]], "")
                if len(r) > 0:
                    pat="\s*(and|&|,)\s*([A-Z][a-zA-Z]+\s+[A-Z]?[.]?\s*[A-Z][a-zA-Z]+)\s*"
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


    # Run through the rows and columns and look at the Notes column  If an APA mailing note is present,
    # move it to a "Mailing" column (which may need to be created).  Remove the text from the Notes column.
    # Find the Notes column. If there is none, we're done.
    def OnPopupPropagateEditor(self, event):  # FanzineIndexPageWindow(FanzineIndexPageEditGen)
        self.wxGrid.SaveEditControlValue()

        if self.tEditors.GetValue() is None or len(self.tEditors.GetValue()) == 0:
            return

        editorscol=FindIndexOfStringInList(self._Datasource.ColHeaders, ["Editor", "Editors"])
        if editorscol is None:
            return

        # Go through the cells in the Editors column and fill in any which are empty with the contents of tEditors
        for row in self._Datasource.Rows:
            if row[editorscol] is None or len(row[editorscol].strip()) == 0:
                row[editorscol]=self.tEditors.GetValue()

        self.RefreshWindow()


#=============================================================
# An individual fanzine to be listed in a fanzine index table
# This is a single row
class FanzineIndexPageTableRow(GridDataRowClass):

    def __init__(self, coldefs: ColDefinitionsList, row: None | list[str]=None):
        GridDataRowClass.__init__(self)
        self.FileSourcePath: str=""
        self._tableColdefs=coldefs
        if row is None:
            self._cells=[""]*len(self._tableColdefs)
        else:
            self._cells=row


    def __str__(self):      # FanzineTableRow(GridDataRowClass)
        return str(self._cells)

    def __len__(self):     # FanzineTableRow(GridDataRowClass)
        return len(self._cells)

    def Extend(self, s: list[str]) -> None:    # FanzineTableRow(GridDataRowClass)
        self._cells.extend(s)

    # Make a deep copy of a FanzineTableRow
    def Copy(self) -> FanzineIndexPageTableRow:      # FanzineTableRow(GridDataRowClass)
        val=FanzineIndexPageTableRow(self._tableColdefs)
        val._cells=[x for x in self._cells]     # Make a new list containing the old cell data
        return val

    # We multiply the cell has by the cell index (+1) so that moves right and left also change the signature
    def Signature(self) -> int:      # FanzineTableRow(GridDataRowClass)
        return sum([x.__hash__()*(i+1) for i, x in enumerate(self._cells)])


    @property
    def CanDeleteColumns(self) -> bool:      # FanzineTableRow(GridDataRowClass)
        return True

    # This deletes a single column from the datasource.
    # It must be implemented here because WxDataGrid doesn't understand the details of the DataSource
    def DelCol(self, icol: int) -> None:      # FanzineTableRow(GridDataRowClass)
        del self._cells[icol]

    @property
    def Cells(self):
        return self._cells
    @Cells.setter
    def Cells(self, val: [str]):
        self._cells=val


    # Get or set a value by name or column number
    #def GetVal(self, name: Union[str, int]) -> Union[str, int]:
    def __getitem__(self, index: str | int | slice) -> str | list[str]:        # FanzineTableRow(GridDataRowClass)

        if isinstance(index, int):
            if index < 0 or  index >= len(self._cells):
                raise IndexError
            return self._cells[index]

        assert not isinstance(index, slice)

        assert isinstance(index, str)

        index=CanonicizeColumnHeaders(index)
        if index not in self._tableColdefs:
            raise IndexError

        index=self._tableColdefs.index(index)
        return self._cells[index]


    #def SetVal(self, nameOrCol: Union[str, int], val: Union[str, int]) -> None:
    def __setitem__(self, index: str | int | slice, value: str | int) -> None:        # FanzineTableRow(GridDataRowClass)
        if isinstance(value, int):
            value=str(value)    # All data is stored as strings

        if isinstance(index, int):
            if index < 0 or  index >= len(self._cells):
                raise IndexError
            self._cells[index]=value
            return

        assert not isinstance(index, slice)

        assert isinstance(index, str)

        index=CanonicizeColumnHeaders(index)
        if index not in self._tableColdefs:
            raise IndexError

        index=self._tableColdefs.index(index)
        self._cells[index]=value
        return


    def IsEmptyRow(self) -> bool:      # FanzineTableRow(GridDataRowClass)
        return all([cell == "" for cell in self._cells])



#*******************************************
# Take a list of column names and generate a list of ColDefs
def ColNamesToColDefs(headers: list[str]) -> ColDefinitionsList:
    colDefs: ColDefinitionsList=ColDefinitionsList([])
    for header in headers:
        # First cannonicize the header
        header=CanonicizeColumnHeaders(header)
        scd=ColDefinition(f"({header})", Type="str", Width=75)  # The default when it's unrecognizable
        if header in gStdColHeaders:
            scd=gStdColHeaders[gStdColHeaders.index(header)]
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
        self._name: str=""
        self._specialTextColor: Optional[Color, bool]=True
        self.TopComments: str=""
        self.Locale: list[str]=[]
        self.FanzineName: str=""
        self._Editors: str=""
        self.Dates: str=""
        self.FanzineType: str=""
        self.Complete=False     # Is this fanzine series complete?
        self.AlphabetizeIndividually=False      # Treat all issues as part of main series
        self.Credits=""         # Who is to be credited for this affair?
        self.Updated: ClassicFanzinesDate=ClassicFanzinesDate(None)


    def Signature(self) -> int:        # FanzineIndexPage(GridDataSource)
        s=0
        if self._colDefs is not None:
            s+=self._colDefs.Signature()
        s+=hash(f"{self._name.strip()};{self.TopComments.strip()};{' '.join(self.Locale).strip()}")
        s+=hash(f"{self.TopComments.strip()};{' '.join(self.Locale).strip()}")
        s+=hash(f"{self.FanzineName};{self.Editors};{self.Dates};{self.FanzineType};{self.Credits};{self.Complete}{self.AlphabetizeIndividually}")
        s+=sum([x.Signature()*(i+1) for i, x in enumerate(self._fanzineList)])
        s+=hash(self._specialTextColor)
        return s


    # Inherited from GridDataSource
    @property
    def Rows(self) -> list[FanzineIndexPageTableRow]:        # FanzineIndexPage(GridDataSource)
        return self._fanzineList
    @Rows.setter
    def Rows(self, rows: list) -> None:        # FanzineIndexPage(GridDataSource)
        self._fanzineList=rows


    @property
    def NumRows(self) -> int:        # FanzineIndexPage(GridDataSource)
        return len(self._fanzineList)

    def __getitem__(self, index: int) -> FanzineIndexPageTableRow:        # FanzineIndexPage(GridDataSource)
        return self.Rows[index]

    def __setitem__(self, index: int, val: FanzineIndexPageTableRow) -> None:        # FanzineIndexPage(GridDataSource)
        self._fanzineList[index]=val


    @property
    def SpecialTextColor(self) -> Optional[Color]:        # FanzineIndexPage(GridDataSource)
        return self._specialTextColor
    @SpecialTextColor.setter
    def SpecialTextColor(self, val: Optional[Color]) -> None:        # FanzineIndexPage(GridDataSource)
        self._specialTextColor=val


    def __str__(self) -> str:
        return str(self.Updated)


    def CanAddColumns(self) -> bool:        # FanzineIndexPage(GridDataSource)
        return True


    def InsertEmptyRows(self, insertat: int, num: int=1) -> None:        # FanzineIndexPage(GridDataSource)
        for i in range(num):
            ftr=FanzineIndexPageTableRow(self._colDefs)
            self._fanzineList.insert(insertat+i, ftr)


    @staticmethod
    def SelectNonNavigableStrings(soupstuff) -> list:        # FanzineIndexPage(GridDataSource)
        return [x for x in soupstuff if not isinstance(x, bs4.element.NavigableString)]


    # Download a fanzine index page fanac.org/fanzines/URL and fill in the class
    def GetFanzineIndexPage(self, url: str) -> bool:        # FanzineIndexPage(GridDataSource)
        testServerDirectory=Settings().Get("Test server directory")
        html=None
        if testServerDirectory != "":
            # If there is a test directory, try loading from there, first
            html=FTP().GetFileAsString(f"/{testServerDirectory}/{url}", "index.html")
        if html is None:
            # If that failed (or there wasn't one) load from the default
            html=FTP().GetFileAsString(f"/fanzines/{url}", "index.html")
        if html is None:
            LogError(f"Unable to download 'index.html' from '{url}'")
            return False

        # This is the tag that marks a new-style page.  The version number may someday be significant
        #<!-- fanac fanzine index page V1.0-->
        m=re.search(r"<!-- fanac fanzine index page V([0-9]+\.[0-9]+)-->", html, flags=re.IGNORECASE|re.MULTILINE)
        if m is None:
            return self.GetFanzineIndexPageOld(html)
        version=m.groups()[0]
        return self.GetFanzineIndexPageNew(html, version)


    def GetFanzineIndexPageOld(self, html: str) -> bool:  # FanzineIndexPage(GridDataSource)
        soup=BeautifulSoup(html, 'html.parser')
        body=soup.findAll("body")
        bodytext=str(body)
        _, bodytext=SearchAndReplace(r"(<script>.+?</script>)", bodytext, "", ignorenewlines=True)

        tables=body[0].findAll("table")
        top=tables[0]
        theTable=tables[2]
        bottom=tables[3]

        locale="(not found)"
        localeStuff=body[0].findAll("fanac-type")
        if len(localeStuff) > 0:
            localeStuff=str(localeStuff[0])
            _, localeStuff=SearchAndReplace(r"(</?fanac-type>)", localeStuff, "")
            _, locale=SearchAndReplace(r"(</?h2/?>)", localeStuff, "")

        # Check for the al[phabetize individually flag
        m=re.search(r"<!-- Fanac-keywords: (.*?) -->", str(body[0]), flags=re.DOTALL|re.MULTILINE|re.IGNORECASE)
        if m is not None:
            if len(m.groups()[0]) > 10:     # Arbitrary, since the keyword should be "Alphabetize individually", but has been added by hand so might be mosta nyhting
                self.AlphabetizeIndividually=True

        fanzinename="(not found)"
        editors="(not found)"
        dates="(not found)"
        fanzinetype="(not found)"
        # Extract the fanzine Name, Editors, Dates and Type
        if len(top.findAll("td")) > 1:
            topmatter=top.findAll("td")[1]
            # This looks like:
            # '<td border="none" class="fmz"><h1 class="sansserif">Apollo<br/><h2>Joe Hensley <br/> Lionel Innman<br/><h2>1943 - 1946<br/><br/>Genzine</h2></h2></h1></td>'
            # Split it first by <h[12].
            topmattersplit=re.split(r"</?h[12]/?>", str(topmatter))
            for i, stuff in enumerate(topmattersplit):
                stuff=re.sub(r"</?br/?>", "\n", stuff)
                _, stuff=SearchAndReplace(r"(<.*?>)", stuff, "")
                topmattersplit[i]=stuff
            topmattersplit=[x.replace("\n\n", "\n").removesuffix("\n") for x in topmattersplit if x != ""]
            fanzinename=topmattersplit[0]
            editors=topmattersplit[1].split("\n")
            dates, fanzinetype=topmattersplit[2].split("\n")

        # Now interpret the table to generate the column headers and data rows
        theRows=theTable.findAll("tr")
        headers: list[str]=[]
        if len(theRows) > 0:
            row0=theRows[0].findAll("th")
            if len(row0) > 0:
                headers=[RemoveAllHTMLLikeTags(str(x)) for x in row0]
        # self.rows=rows
        # self.cols=headers
        # And construct the grid
        # Column #1 is always a link to the fanzine, and we split this into two parts, the URL and the display text
        # We prepend a URL column before the Issue column. This will hold the filename which is the URL for the link
        self._colDefs=ColDefinitionsList([ColDefinition("URL", 100, "URL", IsEditable.Maybe)])
        self._colDefs.append(ColNamesToColDefs(headers))

        rows: list[list[str]]=[]
        if len(theRows) > 1:
            for thisrow in theRows[1:]:

                cols=thisrow.findAll("td")
                # We treat column 0 specially, extracting its hyperref and turning it into two
                cols0=str(cols[0])
                _, url, text, _=FindLinkInString(cols0)
                if url == "" and text == "":
                    row=["", cols0]
                else:
                    row=[url, text]
                row.extend([RemoveAllHTMLLikeTags(str(x)) for x in cols[1:]])
                rows.append(row)

        for row in rows:
            self.Rows.append(FanzineIndexPageTableRow(self._colDefs, row) )

        credits="(not found)"
        loc=bodytext.rfind("</table>")
        if loc >= 0:
            lasttext=bodytext[loc+len("</table>"):]
            lasttext=re.split(r"</?br/?", lasttext)
            lasttext=[RemoveAllHTMLLikeTags(x) for x in lasttext]
            lasttext=[x.replace(r"/n", "").replace("\n", "") for x in lasttext]
            lasttext=[x for x in lasttext if len(x) > 0]
            if len(lasttext) == 2:
                credits=lasttext[0]


        Log(f"GetFanzinePageOld():")
        Log(f"     {credits=}")
        Log(f"     {dates=}")
        Log(f"     {editors=}")
        Log(f"     {fanzinetype=}")
        Log(f"     {locale=}")
        Log(f"     {fanzinename=}")
        self.Credits=credits
        self.Dates=dates
        self.Editors=editors
        self.FanzineType=fanzinetype
        self.Locale=locale
        self.FanzineName=fanzinename

        return True


    @property
    def Editors(self):
        return self._Editors
    @Editors.setter
    def Editors(self, val):
        v=val
        if isinstance(val, list):
            if len(val) == 1:
                v=val[0]
            else:
                v=", ".join(val)
        elif ", " in val:
            v="\n".join([x.strip() for x in val.split(", ")])

        self._Editors=v


    def GetFanzineIndexPageNew(self, html: str, version: str) -> bool:

        # f"{self.FanzineName}<BR><H2>{self.Editors}<BR><H2>{self.Dates}<BR><BR>{self.FanzineType}"
        topstuff=ExtractHTMLUsingFanacComments(html, "header")
        if topstuff == "":
            LogError(f"GetFanzineIndexPageNew() failed: ExtractHTMLUsingFanacComments('header')")
            return False
        # Interpret the header
        topstuff=re.sub(r"(\r|\n|<\\?(br|h2)>)+", "\n", topstuff, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE).split("\n")
        if len(topstuff) != 4:
            topstuff+=["","","",""]
        self.FanzineName=topstuff[0]
        self.Editors="\n".join([x.strip() for x in topstuff[1].split(",")])
        self.Dates=topstuff[2]
        self.FanzineType=topstuff[3]

        # f"<H2>{TurnPythonListIntoWordList(self.Locale)}</H2>"
        locale=ExtractHTMLUsingFanacComments(html, "locale")
        if locale == "":
            LogError(f"GetFanzineIndexPageNew() failed: ExtractHTMLUsingFanacComments('Locale')")
            return False
        # Remove the <h2>s that tend to decorate it
        self.Locale=re.sub(r"</?h2>", "", locale, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE).strip()

        keywords=ExtractInvisibleTextUsingFanacComments(html, "keywords").split(",")
        keywords=[x.strip() for x in keywords]
        for keyword in keywords:
            if keyword == "Alphabetize individually":
                self.AlphabetizeIndividually=True
            if keyword == "Complete":
                self.Complete=True

        comments=ExtractHTMLUsingFanacComments(html, "topcomments")
        if comments is not None:
            self.TopComments=comments.replace("<br>", "\n")

        # Now interpret the table to generate the column headers and data rows
        headers=ExtractHTMLUsingFanacComments(html, "table-headers")
        if headers == "":
            LogError(f"GetFanzineIndexPageNew() failed: ExtractHTMLUsingFanacComments('table-headers')")
            return False
        # Interpret the column headers
        # f "\n<TR>\n<TH>{self.ColHeaders[1]}</TH>\n"...insert+=f"<TH>{header}</TH>\n" (repeats)..."</TR>\n"
        headers=re.findall(r"<TH>(.+?)</TH>", headers, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE)
        self._colDefs=ColNamesToColDefs(headers)
        # Column #1 is always a link to the fanzine, and we split this into two parts, the URL and the display text
        # We prepend a URL column before the Issue column. This will hold the filename which is the URL for the link
        self._colDefs=ColDefinitionsList([ColDefinition("URL", 100, "URL", IsEditable.Maybe)])+self._colDefs

        self.Created=ClassicFanzinesDate(ExtractInvisibleTextInsideFanacComment(html, "created"))
        self.Updated=ClassicFanzinesDate(ExtractInvisibleTextInsideFanacComment(html, "updated"))

        # Now the rows
        rows=ExtractHTMLUsingFanacComments(html, "table-rows")
        rows=re.findall(r"<TR>(.+?)</TR>", rows, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE)
        if rows == "":
            LogError(f"GetFanzineIndexPageNew() failed: ExtractHTMLUsingFanacComments('table-rows')")
            return False
        # Interpret the rows
        for row in rows:
            row=re.findall(r"<TD(:?.*?)>(.*?)</TD>", row, flags=re.DOTALL|re.MULTILINE|re.IGNORECASE)
            cols=[x[1] for x in row]
            # We treat column 0 specially, extracting its hyperref and turning it into two
            cols0=str(cols[0])
            _, url, text, _=FindLinkInString(cols0)
            if url == "" and text == "":
                cols=["", cols0].extend(cols[1:])
            else:
                cols=[url, text]+cols[1:]

            row=[RemoveAllHTMLLikeTags(str(x)) for x in cols]
            self.Rows.append(FanzineIndexPageTableRow(self._colDefs, row) )

        self.Credits=ExtractHTMLUsingFanacComments(html, "scan").strip()

        Log(f"GetFanzinePageNew():")
        Log(f"     {self.Credits=}")
        Log(f"     {self.Dates=}")
        Log(f"     {self.Editors=}")
        Log(f"     {self.FanzineType=}")
        Log(f"     {self.Locale=}")
        Log(f"     {self.FanzineName=}")

        return True


    # Using the fanzine index page template, create a page and upload it.
    def PutFanzineIndexPage(self, url: str) -> bool:        # FanzineIndexPage(GridDataSource)

        if not os.path.exists("Template - Fanzine Index Page.html"):
            LogError(f"PutFanzineIndexPage() can't find ';'Template - Fanzine Index Page.html' at {os.path.curdir}")
            return False
        with open("Template - Fanzine Index Page.html") as f:
            output=f.read()

        eds=", ".join([x.strip() for x in self.Editors.split("\n")])
        insert=f"{self.FanzineName}<BR><H2>{eds}<BR><H2>{self.Dates}<BR><BR>{self.FanzineType}"
        temp=InsertHTMLUsingFanacComments(output, "header", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url}) failed: InsertHTMLUsingFanacComments('header')")
            return False
        output=temp

        insert=f"<H2>{TurnPythonListIntoWordList(self.Locale)}</H2>"
        temp=InsertHTMLUsingFanacComments(output, "locale", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url}) failed: InsertHTMLUsingFanacComments('Locale')")
            return False
        output=temp

        insert=self.TopComments.replace("\n", "<br>")
        temp=InsertHTMLUsingFanacComments(output, "topcomments", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url}) failed: InsertHTMLUsingFanacComments('topcomments')")
            return False
        output=temp

        keywords=""
        if self.AlphabetizeIndividually:
            keywords+="Alphabetize individually"
        if self.Complete:
            if keywords != "":
                keywords+=", "
            keywords+="Complete"
        temp=InsertInvisibleTextUsingFanacComments(output, "keywords", keywords)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url}) failed: InsertInvisibleTextUsingFanacComments('fanac-keywords')")
            return False
        output=temp

        # Insert an invisible updated datetime
        output=InsertInvisibleTextInsideFanacComment(output, "updated", f"{ClassicFanzinesDate().Now()}")

        # Now interpret the table to generate the column headers and data rows
        # The 1st col is the URL and it gets mixed with ther 2nd to form an Href.
        insert="\n<TR>\n"
        if len(self.ColHeaders) < 2:
            LogError(f"PutFanzineIndexPage({url}) failed: {len(self.ColHeaders)=}")
            return False
        insert+=f"<TH>{self.ColHeaders[1]}</TH>\n"
        for header in self.ColHeaders[2:]:
            insert+=f"<TH>{header}</TH>\n"
        insert+="</TR>\n"
        temp=InsertHTMLUsingFanacComments(output, "table-headers", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url}) failed: InsertHTMLUsingFanacComments('table-headers')")
            return False
        output=temp

        # Now the rows
        insert=""
        for row in self.Rows:
            if row.IsEmptyRow():
                continue
            insert+="\n<TR>"
            insert+=f"\n<TD><a href='{row.Cells[0]}'>{row.Cells[1]}</A></TD>\n"
            for cell in row.Cells[2:]:
                insert+=f"<TD CLASS='left'>{cell}</TD>\n"
            insert+="</TR>\n"
        temp=InsertHTMLUsingFanacComments(output, "table-rows", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url}) failed: InsertHTMLUsingFanacComments('table-rows')")
            return False
        output=temp

        temp=InsertHTMLUsingFanacComments(output, "scan", self.Credits)
        # Different test because we don't always have a credit in the file.
        if len(temp) > 0:
            output=temp

        FTP().PutFileAsString("/Fanzines-test/"+url, "index.html", output, create=True)
        return True




