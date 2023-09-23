from __future__ import annotations

from typing import Optional
import os
import shutil
import wx
import wx.grid
import re

from bs4 import BeautifulSoup
import bs4

import HelpersPackage
from GenGUIClass import FanzineIndexPageEdit
from FTP import FTP

from NewFanzineDialog import NewFanzineWindow

from WxDataGrid import DataGrid, Color, GridDataSource, ColDefinition, ColDefinitionsList, GridDataRowClass
from WxHelpers import OnCloseHandling, ProgressMsg, ProgressMessage
from HelpersPackage import Bailout, IsInt, Int0, ZeroIfNone, MessageBox, RemoveScaryCharacters, SetReadOnlyFlag, ParmDict
from HelpersPackage import  ComparePathsCanonical, FindLinkInString, FindIndexOfStringInList, FindIndexOfStringInList2
from HelpersPackage import RemoveHyperlink, RemoveHyperlinkContainingPattern, CanonicizeColumnHeaders
from HelpersPackage import SearchAndReplace, RemoveAllHTMLLikeTags, InsertUsingFanacComments, TurnPythonListIntoWordList
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


class FanzineIndexPageWindow(FanzineIndexPageEdit):
    def __init__(self, parent, url: str=""):
        FanzineIndexPageEdit.__init__(self, parent)

        self._dataGrid: DataGrid=DataGrid(self.wxGrid)
        self.Datasource=FanzineIndexPage()

        self.url=url

        self.IsNewDirectory=False   # Are we creating a new directory? (Alternative is that we're editing an old one.)

        # Get the default PDF directory
        self.PDFSourcePath=Settings().Get("PDF Source Path", os.getcwd())

        # Position the window on the screen it was on before
        tlwp=Settings().Get("Top Level Window Position")
        if tlwp:
            self.SetPosition(tlwp)
        tlws=Settings().Get("Top Level Windows Size")
        if tlws:
            self.SetSize(tlws)

        self.Datasource.targetDirectory=""

        self._signature=0   # We need this member. ClearMainWindow() will initialize it

        # Load the fanzine index page
        with ProgressMsg(parent, f"Downloading Fanzine Index Page: {url}"):
            self.failure=False
            if not self.Datasource.GetFanzineIndexPage(url):
                self.failure=True
                return

        # Add the various values into the dialog
        self.tCredits.SetValue(self.Datasource.Credits)
        self.tDates.SetValue(self.Datasource.Dates)
        self.tEditors.SetValue(", ".join(self.Datasource.Editors))
        self.tFanzineName.SetValue(self.Datasource.FanzineName)
        if self.Datasource.FanzineType in self.tFanzineType.Items:
            self.tFanzineType.SetSelection(self.tFanzineType.Items.index(self.Datasource.FanzineType))
        self.tLocaleText.SetValue(self.Datasource.Locale)
        
        # Now load the fanzine issue data
        self._dataGrid.HideRowLabels()

        self._dataGrid.NumCols=self.Datasource.NumCols
        self._dataGrid.AppendRows(self.Datasource.NumRows)
        # for i in range(self.Datasource.NumCols):
        #     self.wxGrid._colDefs.append(ColDefinition("", IsEditable="no"))

        self._dataGrid.RefreshWxGridFromDatasource()
        self.MarkAsSaved()
        self.RefreshWindow()

        self.Show(True)


    @property
    def Datasource(self) -> FanzineIndexPage:       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        return self._Datasource
    @Datasource.setter
    def Datasource(self, val: FanzineIndexPage):
        self._Datasource=val
        self._dataGrid.Datasource=val


    # Look at information available and color buttons and fields accordingly.
    def ColorFields(self):                      # FanzineIndexPageWindow(FanzineIndexPageEdit)

        # Some things are turned on for both EditingOld and CreatingNew
        self.tFanzineName.SetEditable(True)
        self.tEditors.SetEditable(True)
        self.tDates.SetEditable(True)
        self.tFanzineType.Enabled=True
        self.tTopComments.SetEditable(True)
        self.tLocaleText.SetEditable(True)
        self.cbComplete.Enabled=True
        self.cbAlphabetizeIndividually.Enabled=True
        self.wxGrid.Enabled=True

        self.tFanzineName.SetEditable(False)
        # On an old directory, we always have a target defined, so we can always add new issues
        self.bAddNewIssues.Enable(True)

        # Whether or not the save button is enabled depends on what more we are in and what has been filled in.
        self.bSave.Enable(False)
        if self.tFanzineName.GetValue() and len(self.Datasource.Rows) > 0:
            self.bSave.Enable()


    #------------------
    # An override of DataGrids's method ColorCellsByValue() for columns 0 and 1 only
    def ColorCells01ByValue(self, icol: int, irow: int):            # FanzineIndexPageWindow(FanzineIndexPageEdit)
        if icol != 0 and icol != 1:
            return
        if icol < 0 or icol >= self.Datasource.NumCols:
            return
        if irow < 0 or irow >= self.Datasource.NumRows:
            return


        # The coloring depends on the contents of the cell *pair* self.Datasource.Rows[irow][0:1]
        # We will turn the contents of those cells into LST format and back again.  If they pass unchanged, then we color them white
        # If they change (other than trivial whitespace) we color them pink
        cells=self.Datasource.Rows[irow][0:2]

        # Both empty is just fine.
        if cells[0] == "" and cells[1] == "":
            return

        return


    def OnExitClicked(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.OnClose(event)


    def OnClose(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        if not self.OKToClose(event):
            return

        # Save the window's position
        pos=self.GetPosition()
        Settings().Put("Top Level Window Position", (pos.x, pos.y))
        size=self.GetSize()
        Settings().Put("Top Level Windows Size", (size.width, size.height))

        self.Destroy()


    # The user has requested that the dialog be closed or wiped and reloaded.
    # Check to see if it has unsaved information.
    # If it does, ask the user if he wants to save it first.
    def OKToClose(self, event) -> bool:             # FanzineIndexPageWindow(FanzineIndexPageEdit)
        if not self.NeedsSaving():
            return True

        if not OnCloseHandling(event, self.NeedsSaving(), "The LST file has been updated and not yet saved. Dispose anyway?"):
            self.MarkAsSaved()  # The contents have been declared doomed, so mark it as saved so as not to trigger any more queries.
            return True

        return False


    def OnAddNewIssues(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)

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

        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()


    #--------------------------
    # Check the rows to see if any of the files is a pdf
    # If a pdf is found possibly add a PDF column and fill the PDF column in for those rows.
    def FillInPDFColumn(self) -> None:              # FanzineIndexPageWindow(FanzineIndexPageEdit)
        iPdf=self.AddOrDeletePDFColumnIfNeeded()
        if iPdf != -1:
            for i, row in enumerate(self.Datasource.Rows):
                filename=row[0]
                if filename.lower().endswith(".pdf"):
                    row[iPdf]="PDF"


    #--------------------------
    # Check the rows to see if any of the files are a pdf
    # If a pdf is found possibly add a PDF column and fill the PDF column in for those rows.
    def FillInPagesColumn(self) -> None:                # FanzineIndexPageWindow(FanzineIndexPageEdit)
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
    def AddOrDeletePDFColumnIfNeeded(self) -> int:              # FanzineIndexPageWindow(FanzineIndexPageEdit)
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
    def StandardizeColumns(self) -> None:               # FanzineIndexPageWindow(FanzineIndexPageEdit)

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
    # Initialize the main window to empty
    # This also initiazes the datasource
    def ClearMainWindow(self):       # FanzineIndexPageWindow(FanzineIndexPageEdit)

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


    # ------------------
    # Create a new, empty LST file
    def OnCreateNewFanzineDir(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        if not self.OKToClose(event):
            return

        dlg=NewFanzineWindow(None, self.RootDirectoryPath)
        dlg.ShowModal()
        dlg.Destroy()
        if dlg.Directory != "":

            self.ClearMainWindow()

            self.Datasource.TargetDirectory=dlg.Directory

            self.tFanzineName.SetValue(dlg.FanzineName)

            self.tCredits.SetValue(self.Datasource.Credits.strip())

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

            self.UpdateNeedsSavingFlag()
            self.RefreshWindow()

    #------------------
    # Save an LSTFile object to disk and maybe create a whole new directory
    def OnSave(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        ProgressMessage(self).Show(f"Uploading Fanzine Index Page: {self.url}")
        Log(f"Uploading Fanzine Index Page: {self.url}")
        self.failure=False
        if not self.Datasource.PutFanzineIndexPage(self.url):
            self.failure=True
            Log("Failed\n")
            ProgressMessage(self).Close()
            return
        for row in self.Datasource.Rows:
            if row.FileSourcePath != "":
                ProgressMessage(self).UpdateMessage(f"Uploading file: {row.FileSourcePath}")
                Log(f"Uploading file: {row.FileSourcePath}")
                if not FTP().PutFile(row.FileSourcePath, f"/Fanzines-test/{self.url}/{row.Cells[1]}"):
                    Log("Failed\n")
                    self.failure=True
                    ProgressMessage(self).Close()
                    return
                row.FileSourcePath=""

        Log("All uploads succeeded.")

        self.MarkAsSaved()
        ProgressMessage(self).Close()



    def UpdateNeedsSavingFlag(self):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        s="Editing "+self.url
        if self.NeedsSaving():
            s=s+" *"        # Append a change marker if needed
        self.SetTitle(s)


    def RefreshWindow(self, DontRefreshGrid: bool=False)-> None:       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.UpdateNeedsSavingFlag()

        if not DontRefreshGrid:
            self._dataGrid.RefreshWxGridFromDatasource()
        self.ColorFields()


    # ----------------------------------------------
    # Used to determine if anything has been updated
    def Signature(self) -> int:       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        return self.Datasource.Signature()


    def MarkAsSaved(self):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._signature=self.Signature()
        self.UpdateNeedsSavingFlag()


    def NeedsSaving(self):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        return self._signature != self.Signature()


    # This method updates the local directory name by computing it from the fanzine name.  It only applies when creating a new LST file
    def OnFanzineNameChar(self, event):
        return
        # # The only time we update the local directory
        # fname=AddChar(self.tFanzineName.GetValue(), event.GetKeyCode())
        # self.tFanzineName.SetValue(fname)
        # self.tFanzineName.SetInsertionPoint(999)    # Make sure the cursor stays at the end of the string


    def OnFanzineName(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.Datasource.FanzineName=self.tFanzineName.GetValue()
        self.RefreshWindow(DontRefreshGrid=True)


    def OnEditors(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.Datasource.Editors=self.tEditors.GetValue()
        self.RefreshWindow(DontRefreshGrid=True)


    def OnDates(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.Datasource.Dates=self.tDates.GetValue()
        self.RefreshWindow(DontRefreshGrid=True)


    def OnFanzineType(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)

        # self.tCredits.SetValue(self.Datasource.Credits)
        # self.tDates.SetValue(self.Datasource.Dates)
        # self.tEditors.SetValue(", ".join(self.Datasource.Editors))
        # self.tFanzineName.SetValue(self.Datasource.FanzineName)
        self.tFanzineType.SetValue(self.Datasource.FanzineType)
        # self.tLocaleText.SetValue(self.Datasource.Locale)
        self.RefreshWindow(DontRefreshGrid=True)

    #------------------
    def OnTopComments(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        if self.Datasource.TopComments is not None and len(self.Datasource.TopComments) > 0:
            self.Datasource.TopComments=self.tTopComments.GetValue().split("\n")
        else:
            self.Datasource.TopComments=[self.tTopComments.GetValue().strip()]

        self.RefreshWindow(DontRefreshGrid=True)

    # ------------------
    def OnCheckComplete(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.Datasource.Complete=self.cbComplete.GetValue()
        Log(f"OnCheckComplete(): {self.Datasource.Complete=} and {self.Datasource.AlphabetizeIndividually=}")
        self.RefreshWindow(DontRefreshGrid=True)

    # ------------------
    def OnCheckAlphabetizeIndividually(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.Datasource.AlphabetizeIndividually=self.cbAlphabetizeIndividually.GetValue()
        Log(f"OnCheckAlphabetizeIndividually(): {self.Datasource.Complete=} and {self.Datasource.AlphabetizeIndividually=}")
        self.RefreshWindow(DontRefreshGrid=True)
        # Don't need to refresh because nothing changed


    #------------------
    def OnTextLocale(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.Datasource.Locale=self.tLocaleText.GetValue().split("\n")
        self.RefreshWindow(DontRefreshGrid=True)

    #------------------
    def OnCredits(self, event):
        self.Datasource.Credits=self.tCredits.GetValue().strip()
        self.RefreshWindow(DontRefreshGrid=True)

    #-------------------
    def OnKeyDown(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._dataGrid.OnKeyDown(event) # Pass event to WxDataGrid to handle
        self.UpdateNeedsSavingFlag()

    #-------------------
    def OnKeyUp(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._dataGrid.OnKeyUp(event) # Pass event to WxDataGrid to handle

    #------------------
    def OnGridCellChanged(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._dataGrid.OnGridCellChanged(event)  # Pass event handling to WxDataGrid

        if event.GetCol() == 0:    # If the Filename changes, we may need to fill in the PDF column
            self.FillInPDFColumn()
            self.FillInPagesColumn()
        self.RefreshWindow()

    #------------------
    def OnGridCellRightClick(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        # Do generic RMB on grid processing
        self._dataGrid.OnGridCellRightClick(event, self.m_GridPopup)

        # Call the RMB handler
        self.RMBHandler(True, event)

    # ------------------
    def OnGridLabelLeftClick(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._dataGrid.OnGridLabelLeftClick(event)

    #------------------
    def OnGridLabelRightClick(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        # Do generic RMB on grid processing
        self._dataGrid.OnGridCellRightClick(event, self.m_GridPopup)

        # Call the RMB handler
        self.RMBHandler(False, event)

    # RMB click handling for grid and grid label clicks
    def RMBHandler(self, isCellClick: bool, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
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

        Enable("Tidy Up Columns")

        if self.Datasource.ColHeaders[self._dataGrid.clickedColumn] == "Editor" and self.tEditors.GetValue() is not None and len(self.tEditors.GetValue()) > 0:
            Enable("Propagate Editor")

        # Pop the menu up.
        self.PopupMenu(self.m_GridPopup)


    # ------------------
    # Extract 'scanned by' information from the Notes column, if any
    def ExtractScanner(self, col):       # FanzineIndexPageWindow(FanzineIndexPageEdit)

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
                    row[scannedCol]+="; "     # Use a semi-colon separator if there was already something there
                row[scannedCol]+=m.groups()[0]

                note=re.sub(pattern, "", note)  # Delete the matched text from the note
                note=re.sub("^([ ,]*)", "", note)          # Now remove leading and trailing spans of spaces and commas from the note.
                note=re.sub("([ ,]*)$", "", note)
                row[notesCol]=note

        # And redisplay
        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()

    def OnPopupCopy(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._dataGrid.OnPopupCopy(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow(DontRefreshGrid=True)

    def OnPopupPaste(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._dataGrid.OnPopupPaste(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupEraseSelection(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._dataGrid.OnPopupEraseSelection(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupDelCol(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        if self.Datasource.Element.CanDeleteColumns:
            self._dataGrid.DeleteSelectedColumns() # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupDelRow(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._dataGrid.DeleteSelectedRows() # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupInsertRow(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        irow=self._dataGrid.clickedRow
        # Insert an empty row just before the clicked row
        rows :[FanzineIndexPageTableRow]=[]
        if irow > 0:
            rows=self.Datasource.Rows[:irow]
        rows.append(FanzineIndexPageTableRow(self.Datasource.ColDefs))
        rows.extend(self.Datasource.Rows[irow:])
        self.Datasource.Rows=rows
        self.RefreshWindow()

    def OnPopupRenameCol(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
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
    def PseudonumericSort(self, x: str) -> float:
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
    def MailingSort(self, h: str) -> int:
        if len(h.strip()) == 0:
            return 0
        # First, strip the surrounding HTML
        h=RemoveHyperlink(h)
        m=re.match("^[ a-zA-Z0-9-]* ([0-9]+)[a-zA-Z]?\s*$", h)
        if m:
            return Int0(m.groups()[0])
        return 0


    def OnPopupSortOnSelectedColumn(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.wxGrid.SaveEditControlValue()
        # We already know that only a single column is selected because that's the only time this menu item is enabled and can be called
        _, col, _, _=self._dataGrid.SelectionBoundingBox()
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

    def OnPopupInsertColLeft(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._dataGrid.OnPopupInsertColLeft(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupInsertColRight(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self._dataGrid.OnPopupInsertColRight(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupExtractScanner(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.wxGrid.SaveEditControlValue()
        self.ExtractScanner(self.Datasource.ColDefs.index("Notes"))
        self.RefreshWindow()

    def OnPopupTidyUpColumns(self, event):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
        self.wxGrid.SaveEditControlValue()
        self.ExtractApaMailings()
        self.FillInPDFColumn()
        self.FillInPagesColumn()
        self.StandardizeColumns()
        self.RefreshWindow()


    # Run through the rows and columns and look at the Notes column  If an APA mailing note is present,
    # move it to a "Mailing" column (which may need to be created).  Remove the text from the Notes column.
    # Find the Notes column. If there is none, we're done.
    def ExtractApaMailings(self):       # FanzineIndexPageWindow(FanzineIndexPageEdit)
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

            # First look for a mailing name inside a hyperlink and, if found, remove the hyperlink (we'll add them back when we save the LST file)
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
    def OnPopupExtractEditor(self, event):  # FanzineIndexPageWindow(FanzineIndexPageEdit)
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
    def OnPopupPropagateEditor(self, event):  # FanzineIndexPageWindow(FanzineIndexPageEdit)
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

        if type(index) is int:
            if index < 0 or  index >= len(self._cells):
                raise IndexError
            return self._cells[index]

        assert type(index) is not slice

        assert type(index) is str

        index=CanonicizeColumnHeaders(index)
        if index not in self._tableColdefs:
            raise IndexError

        index=self._tableColdefs.index(index)
        return self._cells[index]


    #def SetVal(self, nameOrCol: Union[str, int], val: Union[str, int]) -> None:
    def __setitem__(self, index: str | int | slice, value: str | int) -> None:        # FanzineTableRow(GridDataRowClass)
        if type(value) is int:
            value=str(value)    # All data is stored as strings

        if type(index) is int:
            if index < 0 or  index >= len(self._cells):
                raise IndexError
            self._cells[index]=value
            return

        assert type(index) is not slice

        assert type(index) is str

        index=CanonicizeColumnHeaders(index)
        if index not in self._tableColdefs:
            raise IndexError

        index=self._tableColdefs.index(index)
        self._cells[index]=value
        return


    def IsEmptyRow(self) -> bool:      # FanzineTableRow(GridDataRowClass)
        return all([cell == "" for cell in self._cells])


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
        self.TopComments: list[str]=[]
        self.Locale: list[str]=[]
        self.FanzineName: str=""
        self.Editors: str=""
        self.Dates: str=""
        self.FanzineType: str=""
        self.Complete=False     # Is this fanzine series complete?
        self.AlphabetizeIndividually=False      # Treat all issues as part of main series
        self.Credits=""         # Who is to be credited for this affair?


    def Signature(self) -> int:        # FanzineIndexPage(GridDataSource)
        s=self._colDefs.Signature()
        s+=hash(f"{self._name.strip()};{' '.join(self.TopComments).strip()};{' '.join(self.Locale).strip()}")
        s+=hash(f"{' '.join(self.TopComments).strip()};{' '.join(self.Locale).strip()}")
        s+=hash(f"{self.FanzineName};{self.Editors};{self.Dates};{self.FanzineType};{self.Credits};{self.Complete}{self.AlphabetizeIndividually}")
        s+=self._colDefs.Signature()
        s+=sum([x.Signature()*(i+1) for i, x in enumerate(self._fanzineList)])
        s+=hash(self._specialTextColor)+self._colDefs.Signature()
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

    def CanAddColumns(self) -> bool:        # FanzineIndexPage(GridDataSource)
        return True

    def InsertEmptyRows(self, insertat: int, num: int=1) -> None:        # FanzineIndexPage(GridDataSource)
        for i in range(num):
            ftr=FanzineIndexPageTableRow(self._colDefs)
            self._fanzineList.insert(insertat+i, ftr)

    def SelectNonNavigableStrings(self, soupstuff) -> list:        # FanzineIndexPage(GridDataSource)
        return [x for x in soupstuff if type(x) is not bs4.element.NavigableString]


    # Read a fanzine index page fanac.org/fanzines/URL and fill in the class
    def GetFanzineIndexPage(self, url: str) -> bool:        # FanzineIndexPage(GridDataSource)
        html=FTP().GetFileAsString("/Fanzines-test/"+url, "index.html")
        if html is None:
            LogError(f"Unable to download 'index.html' from '/Fanzines-test/{url}'")
            return False

        # This is the tag that makes a new-style page.  The version number may somday be significant
        m=re.match(r"<!--\s+fanac\s+fanzines+indexs+pages+V([0-9]+\.[0-9]+)-->", html, flags=re.IGNORECASE)
        if m is None:
            return self.GetFanzineIndexPageOld(html)

        return self.GetFanzineIndexPageNew(html)

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
        self._colDefs: ColDefinitionsList=ColDefinitionsList([])
        for header in headers:
            # First cannonicize the header
            header=CanonicizeColumnHeaders(header)
            scd=ColDefinition(f"({header})", Type="str", Width=75)  # The default when it's unrecognizable
            if header in gStdColHeaders:
                scd=gStdColHeaders[gStdColHeaders.index(header)]
            self._colDefs.append(scd)

        # Column #1 is always a link to the fanzine, and we split this into two parts, the URL and the display text
        # The first step is to prepend a URL column to the start before the Issue column
        temp=ColDefinitionsList([ColDefinition("URL", 100, "URL", "yes")])
        temp.append(self._colDefs)
        self._colDefs=temp

        rows: list[list[str]]=[]
        if len(theRows) > 1:
            for thisrow in theRows[1:]:
                row=[]
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
        i=0

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


        Log(f"GetFanzinePage({url}):")
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

    def GetFanzineIndexPageNew(self, html: str ) -> bool:
        return False


    # Read a fanzine index page fanac.org/fanzines/URL and fill in the class
    def PutFanzineIndexPage(self, url: str) -> bool:        # FanzineIndexPage(GridDataSource)

        output=""
        if not os.path.exists("Fanzine Page Template.html"):
            LogError(f"PutFanzineIndexPage() can't load ';'Fanzine Page Template.html' at {os.path.curdir}")
            return False
        with open("Fanzine Page Template.html") as f:
            output=f.read()

        insert=f"{self.FanzineName}<BR><H2>{self.Editors}<BR><H2>{self.Dates}<BR><BR>{self.FanzineType}"
        temp=InsertUsingFanacComments(output, "header", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url} failed: InsertUsingFanacComments('header')")
            return False
        output=temp

        insert=f"<H2>{TurnPythonListIntoWordList(self.Locale)}</H2>"
        temp=InsertUsingFanacComments(output, "locale", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url} failed: InsertUsingFanacComments('Locale')")
            return False
        output=temp

        # Now interpret the table to generate the column headers and data rows
        # The 1st col is the URL and it gets mixed with ther 2nd to form an Href.
        insert="\n<TR>\n"
        if len(self.ColHeaders) < 2:
            LogError(f"PutFanzineIndexPage({url} failed: {len(self.ColHeaders)=}")
            return False
        insert+=f"<TH>{self.ColHeaders[1]}</TH>\n"
        for header in self.ColHeaders[2:]:
            insert+=f"<TH>{header}</TH>\n"
        insert+="</TR>\n"
        temp=InsertUsingFanacComments(output, "table-headers", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url} failed: InsertUsingFanacComments('table-headers')")
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
        temp=InsertUsingFanacComments(output, "table-rows", insert)
        if temp == "":
            LogError(f"PutFanzineIndexPage({url} failed: InsertUsingFanacComments('table-rows')")
            return False
        output=temp

        temp=InsertUsingFanacComments(output, "scan", self.Credits)
        # Different test because we don't always have a credit in the file.
        if len(temp) > 0:
            output=temp

        FTP().PutFileAsString("/Fanzines-test/"+url, "index-new.html", output)
        return True




