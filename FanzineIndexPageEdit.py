from __future__ import annotations

from enum import Enum
from typing import Union, Optional

import os
import shutil
import wx
import wx.grid

import HelpersPackage
from GenGUIClass import FanzineIndexPageEdit
from FTP import FTP

from NewFanzineDialog import NewFanzineWindow

from WxDataGrid import DataGrid, Color, GridDataSource, ColDefinition, ColDefinitionsList, GridDataRowClass
from WxHelpers import OnCloseHandling, ProgressMsg, ProgressMessage, AddChar, MessageBoxInput
from LSTFile import *
from HelpersPackage import Bailout, IsInt, Int0, ZeroIfNone, MessageBox, RemoveScaryCharacters, SetReadOnlyFlag, ParmDict
from HelpersPackage import  ComparePathsCanonical, FindLinkInString, FindIndexOfStringInList, FindIndexOfStringInList2
from HelpersPackage import RemoveHyperlink, SplitOnSpan, RemoveArticles, RemoveHyperlinkContainingPattern
from PDFHelpers import GetPdfPageCount
from Log import Log as RealLog
from Settings import Settings
from FanzineIssueSpecPackage import MonthNameToInt



class EditMode(Enum):
    NoneSelected=0
    CreatingNew=1
    EditingOld=2


class FanzineIndexPageWindow(FanzineIndexPageEdit):
    def __init__(self, parent, url: str=""):
        FanzineIndexPageEdit.__init__(self, parent)

        self._dataGrid: DataGrid=DataGrid(self.wxGrid)
        self.Datasource=FanzineIndexPage()      # Note that this is an empty instance

        self._dataGrid._ColorCellByValue=self.ColorCells01ByValue

        self.IsNewDirectory=False   # Are we creating a new directory? (Alternative is that we're editing an old one.)

        self.lstFilename: str=""
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

        # The edit mode we are presently in.
        self.Editmode: EditMode=EditMode.NoneSelected

        self._signature=0   # We need this member. ClearMainWindow() will initialize it

        self.ClearMainWindow()
        self.RefreshWindow()

        self.Show(True)


    @property
    def Datasource(self) -> FanzineIndexPage:       # MainWindow(MainFrame)
        return self._Datasource
    @Datasource.setter
    def Datasource(self, val: FanzineIndexPage):
        self._Datasource=val
        self._dataGrid.Datasource=val


    # Look at information available and color buttons and fields accordingly.
    def ColorFields(self):

        # If neither button has been pressed, we are in EditMode NoneSelected and everything else is suppressed.
        if self.Editmode == EditMode.NoneSelected:
            self.bAddNewIssues.Enable(False)
            self.tEditors.SetEditable(False)
            self.tDates.SetEditable(False)
            self.tFanzineType.Enabled=False
            self.tTopComments.SetEditable(False)
            self.tLocaleText.SetEditable(False)
            self.cbComplete.Enabled=False
            self.cbAlphabetizeIndividually.Enabled=False
            self.wxGrid.Enabled=False
            self.tDirectoryServer.SetEditable(False)
            self.tFanzineName.SetEditable(False)

            return

        # OK, one or the other edit button has been pressed.  Adjust editing and coloring accordingly

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

        # The basic split is whether we are editing an existing LST or creating a new directory
        if self.Editmode == EditMode.EditingOld:
            self.tDirectoryServer.SetEditable(False)
            self.tFanzineName.SetEditable(False)
            # On an old directory, we always have a target defined, so we can always add new issues
            self.bAddNewIssues.Enable(True)

        if self.Editmode == EditMode.CreatingNew:
            self.tDirectoryServer.SetEditable(True)
            self.tFanzineName.SetEditable(True)
            self.bAddNewIssues.Enable(True)

        # Whether or not the save button is enabled depends on what more we are in and what has been filled in.
        self.bSave.Enable(False)
        if self.Editmode == EditMode.CreatingNew:
            if len(self.tDirectoryServer.GetValue()) > 0 and len(self.tFanzineName.GetValue()) > 0 and len(self.Datasource.Rows) > 0:
                self.bSave.Enable()

        if self.Editmode == EditMode.EditingOld:
            if self.tFanzineName.GetValue() and len(self.Datasource.Rows) > 0:
                self.bSave.Enable()


    #------------------
    # An override of DataGrids's method ColorCellsByValue() for columns 0 and 1 only
    def ColorCells01ByValue(self, icol: int, irow: int):
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

        val=LSTFile.RowToLST(cells)
        #Log(f"1: {val=}")
        if val == "":
            self._dataGrid.SetCellBackgroundColor(irow, 0, Color.Pink)
            self._dataGrid.SetCellBackgroundColor(irow, 1, Color.Pink)
            return

        val=LSTFile.LSTToRow(val)
        #Log(f"2: {val=}")
        if val == ("", ""):
            self._dataGrid.SetCellBackgroundColor(irow, 0, Color.Pink)
            self._dataGrid.SetCellBackgroundColor(irow, 1, Color.Pink)
            return

        return


    #------------------
    # Open a dialog to allow the user to select an LSTFile on disk.
    # Load it (and some other stuff) into self's 'LSFFile() object
    def LoadLSTFile(self, path: str, lstfilename: str):       # MainWindow(MainFrame)

        # Clear out any old information from form.
        self.ClearMainWindow()
        self.Editmode=EditMode.EditingOld
        self.RefreshWindow()

        self.lstFilename=lstfilename
        Log(f"ClearMainWindow() initializes {self.lstFilename=}")
        lstfile=LSTFile()   # Start with an empty LSTfile

        # Read the lst file
        pathname=os.path.join(path, lstfilename)
        try:
            lstfile.Load(pathname)
        except Exception as e:
            LogError(f"MainWindow: Failure reading LST file '{pathname}'")
            Bailout(e, f"MainWindow: Failure reading LST file '{pathname}'", "LSTError")

        if len(lstfile.Rows) == 0:
            Bailout(None, f"LST file {pathname} appears to have no rows.  It cannot be read.", "LST file load error")


        self._dataGrid.NumCols=0
        self._dataGrid.DeleteRows(0, self._dataGrid.NumRows)
        self._dataGrid.Grid.ScrollLines(-999)   # Scroll down a long ways to show start of file

        # Copy the row data over into the Datasource class
        # Because the LST data tends to be especially sloppy in the column count (extra or missing semicolons),
        # we expand to cover the maximum number of columns found so as to drop nothing.
        FTRList: list[FanzineIndexPageTableRow]=[FanzineIndexPageTableRow(row) for row in lstfile.Rows]
        # Find the longest row and lengthen all the rows to that length
        maxlen=max([len(row) for row in FTRList])
        maxlen=max(maxlen, len(lstfile.ColumnHeaders))
        if len(lstfile.ColumnHeaders) < maxlen:
            lstfile.ColumnHeaders.extend([""]*(maxlen-len(lstfile.ColumnHeaders)))
        for row in FTRList:
            if len(row) < maxlen:
                row.Extend([""]*(maxlen-len(row)))

        # Turn the Column Headers into the grid's columns
        self.Datasource.ColDefs=ColDefinitionsList([])
        for name in lstfile.ColumnHeaders:
            if name == "":
                self.Datasource.ColDefs.append(ColDefinition())
            elif name in self.stdColHeaders:
                name=self.stdColHeaders[name].Preferred
                self.Datasource.ColDefs.append(self.stdColHeaders[name])
            else:
                self.Datasource.ColDefs.append(ColDefinition(name))

        self.Datasource._fanzineList=FTRList
        self.Datasource.AlphabetizeIndividually=lstfile.AlphabetizeIndividually

        self._dataGrid.RefreshWxGridFromDatasource(RetainSelection=False)

        # Fill in the upper stuff
        self.tFanzineName.SetValue(lstfile.FanzineName.strip())
        self.tEditors.SetValue(lstfile.Editors.strip())
        self.tDates.SetValue(lstfile.Dates.strip())

        num=self.tFanzineType.FindString(lstfile.FanzineType)
        if num == -1:
            num=0
        self.tFanzineType.SetSelection(num)
        if len(lstfile.TopComments) > 0:
            self.tTopComments.SetValue("\n".join(lstfile.TopComments))
        if lstfile.Locale:
            self.tLocaleText.SetValue("\n".join(lstfile.Locale))

        if lstfile.FanzineType and lstfile.FanzineType in self.tFanzineType.Items:
            self.tFanzineType.SetSelection(self.tFanzineType.Items.index(lstfile.FanzineType))
        else:
            self.tFanzineType.SetSelection(0)
        self.OnFanzineType(None)        # I don't know why, but SetSelection does not trigger this event

        self.cbAlphabetizeIndividually.SetValue(lstfile.AlphabetizeIndividually)
        self.OnCheckAlphabetizeIndividually(None)  # Need to manually trigger datasource action
        self.cbComplete.SetValue(lstfile.Complete)

        self.ExtractApaMailings()
        self.FillInPDFColumn()
        self.FillInPagesColumn()
        self.StandardizeColumns()


    # Create a new LSTFile from the datasource
    def CreateLSTFileFromDatasourceEtc(self) -> LSTFile:       # MainWindow(MainFrame)

        lstfile=LSTFile()

        # Fill in the upper stuff
        lstfile.FanzineName=self.Datasource.FanzineName
        lstfile.Editors=self.Datasource.Editors
        lstfile.Dates=self.Datasource.Dates
        lstfile.FanzineType=self.Datasource.FanzineType

        lstfile.TopComments=self.Datasource.TopComments
        lstfile.Locale=self.Datasource.Locale

        lstfile.Complete=self.Datasource.Complete
        lstfile.AlphabetizeIndividually=self.Datasource.AlphabetizeIndividually
        Log(f"CreateLSTFileFromDatasourceEtc(): {lstfile.Complete=} and {lstfile.AlphabetizeIndividually=}")

        # Copy over the column headers
        lstfile.ColumnHeaders=self.Datasource.ColHeaders

        # Now copy the grid's cell contents to the LSTFile structure
        lstfile.Rows=[]
        for i in range(self.Datasource.NumRows):
            row=[None]*self.Datasource.NumCols
            for j in range(self.Datasource.NumCols):
                row[j]=self.wxGrid.GetCellValue(i, j)
            lstfile.Rows.append(row)

        return lstfile


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



    def OnAddNewIssues(self, event):       # MainWindow(MainFrame)

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

        # Copy the files from the source directory to the target directory if necessary.
        # Rename them with "safe" names for use on fanac.org (and for Jack's SW) if necessary
        newlyAddedFiles: list[str]=[]
        with ProgressMsg(self, f"Loading..."):
            for file in files:
                # Because we need to remove periods from the filename, we need to temporarily split the extension off so we don't remove that very important period.
                origfullpath, origfilename=os.path.split(file)         # Split to path and filename (including ext)
                f, e=os.path.splitext(origfilename)                    # Remove the extension
                safefilename=RemoveScaryCharacters(f)+e
                safefilename=safefilename.replace("~", "_")     # Deal with a limitation of Jack's SW

                newfilepathname=os.path.join(self.TargetDirectoryPathname, safefilename)
                oldfilepathname=file
                Log(f"CopySelectedFiles: Loading {oldfilepathname}  to  {newfilepathname}")
                ProgressMessage(self).UpdateMessage(f"Loading {os.path.split(oldfilepathname)[1]}")
                # There are two cases: This may be a copy between directories or a rename in the same directory
                if ComparePathsCanonical(self.TargetDirectoryPathname, origfullpath):
                    # It is in the right directory already.  Do we need to rename it?
                    if safefilename == origfilename:
                        Log(f"file {file} is just fine as it stands")
                        newlyAddedFiles.append(safefilename)
                        continue
                    newfilepathname=os.path.join(self.TargetDirectoryPathname, safefilename)
                    Log(f"shutil.move({file}, {newfilepathname}")
                    try:
                        shutil.move(file, newfilepathname)
                        newlyAddedFiles.append(safefilename)
                    except FileNotFoundError:
                        LogError(f"FileNotFound: {file}")
                else:
                    # It's a copy (the normal case)
                    try:
                        shutil.copy(oldfilepathname, newfilepathname)
                        newlyAddedFiles.append(safefilename)
                    except FileNotFoundError:
                        LogError(f"FileNotFound: {oldfilepathname}")

        # The files are all now in the target directory and, if needed, renamed to safe names.
        # We have a list of file names that are in the LSTfile's directory
        # Start by removing any already-existing empty trailing rows
        while self.Datasource.Rows:
            last=self.Datasource.Rows.pop()
            if any([cell != "" for cell in last.Cells]):
                self.Datasource.Rows.append(last)
                break

        # Sort the new files by name and add them to the rows at the bottom
        newlyAddedFiles.sort()
        nrows=self.Datasource.NumRows
        self.Datasource.AppendEmptyRows(len(newlyAddedFiles))
        for i, file in enumerate(newlyAddedFiles):
            self.Datasource.Rows[nrows+i][0]=file

        # Add a PDF column (if needed) and fill in the PDF column and page counts
        self.FillInPDFColumn()
        self.FillInPagesColumn()

        self._dataGrid.RefreshWxGridFromDatasource()
        self.RefreshWindow()


    #--------------------------
    # Check the rows to see if any of the files is a pdf
    # If a pdf is found possibly add a PDF column and fill the PDF column in for those rows.
    def FillInPDFColumn(self) -> None:
        iPdf=self.AddOrDeletePDFColumnIfNeeded()
        if iPdf != -1:
            for i, row in enumerate(self.Datasource.Rows):
                filename=row[0]
                if filename.lower().endswith(".pdf"):
                    row[iPdf]="PDF"


    #--------------------------
    # Check the rows to see if one of any of the files are a pdf
    # If a pdf is found possibly add a PDF column and fill the PDF column in for those rows.
    def FillInPagesColumn(self) -> None:
        iPages=self.Datasource.ColHeaderIndex("pages")
        # Look through the rows and for each PDF which does not have a page count, add the page count
        for i, row in enumerate(self.Datasource.Rows):
            if row[iPages].strip() == "":   # Don't bother with rows that already have page counts
                # Col 0 always contains the filename. If it's a PDF, get its pagecount and fill in that cell
                filename=row[0]
                if filename.lower().endswith(".pdf"):
                    pages=GetPdfPageCount(os.path.join(self.TargetDirectoryPathname, filename))
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



    #------------------
    # Load an LST file from disk into an LSTFile class
    def OnLoadExistingLSTFile(self, event):       # MainWindow(MainFrame)

        if OnCloseHandling(None, self.NeedsSaving(), "The LST file has been updated and not yet saved. Replace anyway?"):
            return
        self.MarkAsSaved()  # OK, the existing contents have been declared doomed.

        self.Editmode=EditMode.EditingOld
        self.tDirectoryServer.SetValue("")

        # Call the File Open dialog to get an LST file
        with wx.FileDialog(self, "Select LST file to load", self.RootDirectoryPath, "", "*.LST", wx.FD_OPEN) as dlg:
            dlg.SetWindowStyle(wx.STAY_ON_TOP)

            if dlg.ShowModal() != wx.ID_OK:
                return False

            targetFilename=dlg.GetFilename()
            targetDirectoryPathname=os.path.split(dlg.GetPath())[0]

        with ProgressMsg(self, f"Loading '{targetFilename}'"):

            self.LoadLSTFile2(targetDirectoryPathname, targetFilename)


    def LoadLSTFile2(self, targetDirectoryPathname, targetFilename):
        # Try to load the LSTFile
        # targetFilename=os.path.relpath(targetDirectoryPathname, start=self.RootDirectoryPath)
        self.LoadLSTFile(targetDirectoryPathname, targetFilename)
        self.lstFilename=targetFilename
        # Get the newly selected target directory's path relative to rootpath
        self.Datasource.TargetDirectory=os.path.relpath(targetDirectoryPathname, start=self.RootDirectoryPath)

        # Rummage through the setup.bld file in the LST file's directory to get Complete and Credits
        complete, credits=self.ReadSetupBld(self.TargetDirectoryPathname)
        if complete is not None:
            self.cbComplete.SetValue(complete)
        else:
            self.cbComplete.SetValue(False)
        self.OnCheckComplete(None)  # Need to manually trigger datasource action
        if credits is not None:
            self.tCredits.SetValue(credits.strip())
            self.Datasource.Credits=credits
        else:
            self.tCredits.SetValue("")
            self.Datasource.Credits=""

        # And see if we can pick up the server directory from setup.ftp
        directory=self.ReadSetupFtp(targetDirectoryPathname)
        if directory != "":
            self.tDirectoryServer.SetValue(directory)
            self.Datasource.ServerDirectory=directory
        self.MarkAsSaved()
        self.RefreshWindow()

    # ------------------
    # Initialize the main window to empty
    # This also initiazes the datasource
    def ClearMainWindow(self):       # MainWindow(MainFrame)

        # Re-initialize the form
        self.lstFilename=""
        self.Datasource.TargetDirectory=""
        self.Datasource.ServerDirectory=""

        # Create default column headers
        self.stdColHeaders: ColDefinitionsList=ColDefinitionsList([
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
                                                              ColDefinition("Scanned BY", Type="str", Width=100),
                                                              ColDefinition("Country", Type="str", Width=50),
                                                              ColDefinition("Editor", Type="str", Width=75),
                                                              ColDefinition("Author", Type="str", Width=75),
                                                              ColDefinition("Mailing", Type="str", Width=75),
                                                              ColDefinition("Repro", Type="str", Width=75)
                                                              ])

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
        self.tDirectoryServer.SetValue("")
        self.cbComplete.SetValue(False)
        self.cbAlphabetizeIndividually.SetValue(False)

        self.Datasource.Credits=Settings().Get("Scanning credits default", default="")

        # Set the signature to the current (empty) state so any change will trigger a request to save on exit
        self.MarkAsSaved()


    # ------------------
    # Create a new, empty LST file
    def OnCreateNewFanzineDir(self, event):       # MainWindow(MainFrame)

        if OnCloseHandling(None, self.NeedsSaving(), "The LST file has been updated and not yet saved. Erase anyway?"):
            return

        dlg=NewFanzineWindow(None, self.RootDirectoryPath)
        dlg.ShowModal()
        dlg.Destroy()
        if dlg.Directory != "":

            self.ClearMainWindow()
            self.Editmode=EditMode.CreatingNew

            self.Datasource.TargetDirectory=dlg.Directory

            self.tFanzineName.SetValue(dlg.FanzineName)
            self.GenerateServerNameFromFanzineName()

            self.tCredits.SetValue(self.Datasource.Credits.strip())

            # Create default column headers
            self._Datasource.ColDefs=ColDefinitionsList([
                self.stdColHeaders["Filename"],
                self.stdColHeaders["Issue"],
                self.stdColHeaders["Whole"],
                self.stdColHeaders["Vol"],
                self.stdColHeaders["Number"],
                self.stdColHeaders["Month"],
                self.stdColHeaders["Day"],
                self.stdColHeaders["Year"],
                self.stdColHeaders["Pages"],
                self.stdColHeaders["Notes"]
            ])

            self.MaybeSetNeedsSavingFlag()
            self.RefreshWindow()

    def OnRenameFanzine(self, event):
        name=MessageBoxInput("Enter the new name for the fanzine", title="Rename Fanzine", initialValue=self.tFanzineName.Value, ignoredebugger=True)
        Log(f"OnRenameFanzine(): {name=}")
        if name is None or len(name.strip()) == 0:
            return

        # The task is to rename the fanzine, but *not* the directory or the LST file
        self.tFanzineName.SetValue(name)


    #------------------
    # Save an LSTFile object to disk and maybe create a whole new directory
    def OnSave(self, event):       # MainWindow(MainFrame)

        if self.Editmode == EditMode.CreatingNew:
            self.CreateNewLSTDirectory()
            self.lstFilename=self.Datasource.TargetDirectory+".lst"
            Log(f"OnSave() initializes {self.lstFilename=}")

        self.SaveExistingLSTFile()

        self.LoadLSTFile2(self.TargetDirectoryPathname, self.lstFilename)


    #------------------
    # Save an existing LST file by simply overwriting what exists.
    def SaveExistingLSTFile(self):       # MainWindow(MainFrame)

        # In normal mode we save each edited LST file by renaming it and the edited version is given the original name
        # In debug more, the original version stays put and the edited version is saved as -new

        newfname=self.lstFilename
        oldname=os.path.join(self.TargetDirectoryPathname, newfname)
        if os.path.exists(oldname):
            newpname=os.path.join(self.TargetDirectoryPathname, os.path.splitext(self.lstFilename)[0]+"-old.LST")

        with ProgressMsg(self, f"Creating {newfname}"):

            # Create an instance of the LSTfile class from the datasource
            lstfile=self.CreateLSTFileFromDatasourceEtc()

            templateDirectory=Settings().Get("Template directory", default=".")
            # Update the existing setup.bld file based on what the user filled in in the main dialog
            if not self.UpdateSetupBld(self.TargetDirectoryPathname):
                if not self.CopyTemplateFile("setup.bld template", "setup.bld", self.TargetDirectoryPathname, templateDirectory):
                    Log(f"Could not create setup.bld using {templateDirectory=}")


            # If there is an old file, rename it
            if os.path.exists(oldname):

                try:
                    i=0
                    # Look for an available new name
                    while os.path.exists(newpname):
                        i+=1
                        newpname=os.path.join(self.TargetDirectoryPathname, f"{os.path.splitext(self.lstFilename)[0]}-old-{i}.LST")
                    os.rename(oldname, newpname)
                except Exception:
                    LogError(f"OnSave fails when trying to rename {oldname} to {newpname}")
                    Bailout(PermissionError, f"OnSave fails when trying to rename {oldname} to {newpname}", "LSTError")

            self.SaveFile(lstfile, oldname)

            if os.path.exists(newpname):
                os.remove(newpname)
            self.SaveFile(lstfile, newpname)
            #End For debugging purposes!!!!!

            self.MarkAsSaved()
            self.RefreshWindow()

    #------------------
    # Create a new fanzine directory and LSTfile
    def CreateNewLSTDirectory(self):       # MainWindow(MainFrame)

        # If a directory was not specified in the main dialog, use the Save dialog to decide where to save it.
        if not self.Datasource.TargetDirectory:
            dlg=wx.DirDialog(self, "Create new directory", "", wx.DD_DEFAULT_STYLE)
            dlg.SetWindowStyle(wx.STAY_ON_TOP)

            if dlg.ShowModal() != wx.ID_OK:
                dlg.Raise()
                dlg.Destroy()
                return False

            self.Datasource.TargetDirectory=dlg.GetPath()
            dlg.Destroy()

        newDirectory=self.TargetDirectoryPathname

        Log(f"ProgressMsg('Creating {self.tFanzineName.GetValue()}')")
        with ProgressMsg(self, f"Creating {self.tFanzineName.GetValue()}"):

            # Copy setup.ftp and setup.bld from the templates source to the new directory.
            templateDirectory=Settings().Get("Template directory", default=".")

            # Look in Settings to find the names of the template files.
            # Copy them from the template directory to the LST file's directory
            if not self.CopyTemplateFile("setup.ftp template", "setup.ftp", newDirectory, templateDirectory):
                return
            if not self.CopyTemplateFile("setup.bld template", "setup.bld", newDirectory, templateDirectory):
                return
            # Edit them based on what the user entered in the main dialog
            if not self.UpdateSetupFtp(newDirectory):
                return
            if not self.UpdateSetupBld(newDirectory):
                return


    def UpdateSetupBld(self, path) -> bool:
        # Read setup.bld, edit it, and save the result back
        # The file consists of lots of lines of the form xxx=yyy
        # We want to edit two of them.
        filename=os.path.join(path, "setup.bld")
        Log(f"Opening {filename}")
        if not os.path.exists(filename):
            LogError(f"{filename} does not exist")
            return False
        with open(filename, "r") as fd:
            lines=fd.readlines()
        RealLog(f"Read {lines=}")
        # Turn the inout lines into a dictionary of key:value pairs.  The value is a tuple of the key in its actual case and the value
        setupbld: ParmDict=ParmDict(CaseInsensitiveCompare=True)
        setupbld.AppendLines(lines)

        # Update with changed values, if any
        if self.Datasource.Credits:
            credits=self.Datasource.Credits.strip()
            if len(credits) > 0:
                if credits[0] != "'" and credits[0] != '"':
                    credits="'"+credits
                if credits[:0] != "'" and credits[:0] != '"':
                    credits=credits+"'"

                setupbld["Credit"]=credits

        if self.cbComplete.GetValue() == 0:
            setupbld["Complete"]="FALSE"
        else:
            setupbld["Complete"]="TRUE"

        HelpersPackage.SetReadOnlyFlag(filename, False)
        # Convert back to an array of lines and write
        lines=setupbld.Lines()
        with open(filename, "w") as fd:
            fd.writelines(lines)

        return True


    def ReadSetupBld(self, path) -> tuple[Optional[bool], Optional[str]]:
        # Read setup.bld, edit it, and save the result back
        # The file consists of lots of lines of the form xxx=yyy
        # We want to edit two of them.
        filename=os.path.join(path, "setup.bld")
        Log(f"Opening {filename}")
        if not os.path.exists(filename):
            return None, None
        with open(filename, "r") as fd:
            lines=fd.readlines()
        Log(f"Read {lines=}")
        credits=None
        complete=None
        for i, line in enumerate(lines):
            m=re.match("^([a-zA-Z0-9_ ]+)=(.*)$", line)
            if m:
                if m.groups()[0].lower().strip() == "credit":
                    credits=m.groups()[1].strip(" \"'")
                if m.groups()[0].lower().strip() == "complete":
                    complete='true' == m.groups()[1].strip(" '").lower()

        return complete, credits


    def UpdateSetupFtp(self, path) -> bool:

        filename=os.path.join(path, "setup.ftp")
        Log(f"UpdateSetupFtp: Opening {filename}")
        if not os.path.exists(filename):
            return False
        with open(filename, "r") as fd:
            lines=fd.readlines()
        found=False
        for i, line in enumerate(lines):
            m=re.match("(^.*/fanzines/)(.*)$", line)
            if m is not None:
                found=True
                lines[i]=m.groups()[0]+self.Datasource.ServerDirectory
        if not found:
            MessageBox("Can't edit setup.ftp. Save failed.")
            Log("CreateLSTDirectory: Can't edit setup.ftp. Save failed.")
            return False

        HelpersPackage.SetReadOnlyFlag(filename, False)

        try:
            with open(filename, "w") as fd:
                Log(f"UpdateSetupFtp: open {filename}")
                fd.writelines(lines)
        except Exception as e:
            Log(f"UpdateSetupFtp exception {e}")
        return True


    # Read the setup.ftp file, returning the name of the server directory or the empty string
    def ReadSetupFtp(self, path) -> str:
        filename=os.path.join(path, "setup.ftp")
        Log(f"Opening {filename}")
        if not os.path.exists(filename):
            return ""
        with open(filename, "r") as fd:
            lines=fd.readlines()
        Log(f"Read {lines=}")
        for i, line in enumerate(lines):
            m=re.match("(^.*/fanzines/)(.*)$", line)
            if m is not None:
                return m.groups()[1]

        return ""


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
        s="Editing "+self.lstFilename
        if self.NeedsSaving():
            s=s+" *"        # Add on a change marker if needed
        self.SetTitle(s)


    def RefreshWindow(self, DontRefreshGrid: bool=False)-> None:       # MainWindow(MainFrame)
        self.MaybeSetNeedsSavingFlag()
        if not DontRefreshGrid:
            self._dataGrid.RefreshWxGridFromDatasource()
        self.ColorFields()


    # ----------------------------------------------
    # Used to determine if anything has been updated
    def Signature(self) -> int:       # MainWindow(MainFrame)
        return self.Datasource.Signature()


    def MarkAsSaved(self):       # MainWindow(MainFrame)
        self._signature=self.Signature()


    def NeedsSaving(self):       # MainWindow(MainFrame)
        return self._signature != self.Signature()


    # This method updates the local directory name by computing it from the fanzine name.  It only applies when creating a new LST file
    def OnFanzineNameChar(self, event):
        if self.Editmode == EditMode.CreatingNew:
            # The only time we update the local directory
            fname=AddChar(self.tFanzineName.GetValue(), event.GetKeyCode())
            self.tFanzineName.SetValue(fname)
            self.GenerateServerNameFromFanzineName()
            self.tFanzineName.SetInsertionPoint(999)    # Make sure the cursor stays at the end of the string


    def GenerateServerNameFromFanzineName(self):
        # Log(f"OnFanzineNameChar: {fname=}  {event.GetKeyCode()}")
        converted=self.tFanzineName.GetValue()
        converted=RemoveArticles(converted)
        converted=RemoveScaryCharacters(converted)
        converted=SplitOnSpan(" _.,", converted)
        converted="_".join(converted)
        self.tDirectoryServer.SetValue(converted)


    def OnFanzineName(self, event):       # MainWindow(MainFrame)
        self.Datasource.FanzineName=self.tFanzineName.GetValue()
        self.RefreshWindow(DontRefreshGrid=True)


    def OnEditors(self, event):       # MainWindow(MainFrame)
        self.Datasource.Editors=self.tEditors.GetValue()
        self.RefreshWindow(DontRefreshGrid=True)


    def OnDates(self, event):       # MainWindow(MainFrame)
        self.Datasource.Dates=self.tDates.GetValue()
        self.RefreshWindow(DontRefreshGrid=True)


    def OnFanzineType(self, event):       # MainWindow(MainFrame)
        self.Datasource.FanzineType=self.tFanzineType.GetString(self.tFanzineType.GetSelection()).strip()
        self.RefreshWindow(DontRefreshGrid=True)

    #------------------
    def OnTopComments(self, event):       # MainWindow(MainFrame)
        if self.Datasource.TopComments is not None and len(self.Datasource.TopComments) > 0:
            self.Datasource.TopComments=self.tTopComments.GetValue().split("\n")
        else:
            self.Datasource.TopComments=[self.tTopComments.GetValue().strip()]

        self.RefreshWindow(DontRefreshGrid=True)

    # ------------------
    def OnCheckComplete(self, event):       # MainWindow(MainFrame)
        self.Datasource.Complete=self.cbComplete.GetValue()
        Log(f"OnCheckComplete(): {self.Datasource.Complete=} and {self.Datasource.AlphabetizeIndividually=}")
        self.RefreshWindow(DontRefreshGrid=True)

    # ------------------
    def OnCheckAlphabetizeIndividually(self, event):       # MainWindow(MainFrame)
        self.Datasource.AlphabetizeIndividually=self.cbAlphabetizeIndividually.GetValue()
        Log(f"OnCheckAlphabetizeIndividually(): {self.Datasource.Complete=} and {self.Datasource.AlphabetizeIndividually=}")
        self.RefreshWindow(DontRefreshGrid=True)
        # Don't need to refresh because nothing changed

    # ------------------
    def OnDirectoryServer(self, event):       # MainWindow(MainFrame)
        self.Datasource.ServerDirectory=self.tDirectoryServer.GetValue()
        self.RefreshWindow(DontRefreshGrid=True)

    #------------------
    def OnTextLocale(self, event):       # MainWindow(MainFrame)
        self.Datasource.Locale=self.tLocaleText.GetValue().split("\n")
        self.RefreshWindow(DontRefreshGrid=True)

    #------------------
    def OnCredits(self, event):
        self.Datasource.Credits=self.tCredits.GetValue().strip()
        self.RefreshWindow(DontRefreshGrid=True)

    #-------------------
    def OnKeyDown(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnKeyDown(event) # Pass event to WxDataGrid to handle
        self.MaybeSetNeedsSavingFlag()

    #-------------------
    def OnKeyUp(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnKeyUp(event) # Pass event to WxDataGrid to handle

    #------------------
    def OnGridCellChanged(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnGridCellChanged(event)  # Pass event handling to WxDataGrid

        if event.GetCol() == 0:    # If the Filename changes, we may need to fill in the PDF column
            self.FillInPDFColumn()
            self.FillInPagesColumn()
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

        Enable("Tidy Up Columns")

        if self.Datasource.ColHeaders[self._dataGrid.clickedColumn] == "Editor" and self.tEditors.GetValue() is not None and len(self.tEditors.GetValue()) > 0:
            Enable("Propagate Editor")

        # Pop the menu up.
        self.PopupMenu(self.m_GridPopup)


    # ------------------
    # Extract 'scanned by' information from the Notes column, if any
    def ExtractScanner(self, col):       # MainWindow(MainFrame)

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

    def OnPopupCopy(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnPopupCopy(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow(DontRefreshGrid=True)

    def OnPopupPaste(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnPopupPaste(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupEraseSelection(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnPopupEraseSelection(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupDelCol(self, event):       # MainWindow(MainFrame)
        if self.Datasource.Element.CanDeleteColumns:
            self._dataGrid.DeleteSelectedColumns() # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupDelRow(self, event):       # MainWindow(MainFrame)
        self._dataGrid.DeleteSelectedRows() # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupInsertRow(self, event):
        irow=self._dataGrid.clickedRow
        # Insert an empty row just before the clicked row
        rows :[FanzineIndexPageTableRow]=[]
        if irow > 0:
            rows=self.Datasource.Rows[:irow]
        rows.append(FanzineIndexPageTableRow([""]*self.Datasource.NumCols))
        rows.extend(self.Datasource.Rows[irow:])
        self.Datasource.Rows=rows
        self.RefreshWindow()

    def OnPopupRenameCol(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnPopupRenameCol(event) # Pass event to WxDataGrid to handle

        # Now we check the column header to see if it iss one of the standard header. If so, we use the std definition for that header
        # (We have to do this here because WxDataGrid doesn't know about header semantics.)
        icol=self._dataGrid.clickedColumn
        cd=self.Datasource.ColDefs[icol]
        if cd.Name in self.stdColHeaders:
            self.Datasource.ColDefs[icol]=self.stdColHeaders[cd.Name]
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


    def OnPopupSortOnSelectedColumn(self, event):       # MainWindow(MainFrame)
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

    def OnPopupInsertColLeft(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnPopupInsertColLeft(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupInsertColRight(self, event):       # MainWindow(MainFrame)
        self._dataGrid.OnPopupInsertColRight(event) # Pass event to WxDataGrid to handle
        self.RefreshWindow()

    def OnPopupExtractScanner(self, event):       # MainWindow(MainFrame)
        self.wxGrid.SaveEditControlValue()
        self.ExtractScanner(self.Datasource.ColDefs.index("Notes"))
        self.RefreshWindow()

    def OnPopupTidyUpColumns(self, event):       # MainWindow(MainFrame)
        self.wxGrid.SaveEditControlValue()
        self.ExtractApaMailings()
        self.FillInPDFColumn()
        self.FillInPagesColumn()
        self.StandardizeColumns()
        self.RefreshWindow()


    # Run through the rows and columns and look at the Notes column  If an APA mailing note is present,
    # move it to a "Mailing" column (which may need to be created).  Remove the text from the Notes column.
    # Find the Notes column. If there is none, we're done.
    def ExtractApaMailings(self):       # MainWindow(MainFrame)
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
                self._Datasource.InsertColumnHeader(-1, self.stdColHeaders["Mailing"])
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
    def OnPopupExtractEditor(self, event):  # MainWindow(MainFrame)
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
                self._Datasource.InsertColumnHeader(-1, self.stdColHeaders["Editor"])
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
    def OnPopupPropagateEditor(self, event):  # MainWindow(MainFrame)
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
# An individual file to be listed under a convention
# This is a single row
class FanzineIndexPageTableRow(GridDataRowClass):

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
    def Copy(self) -> FanzineIndexPageTableRow:      # FanzineTableRow(GridDataRowClass)
        ftr=FanzineIndexPageTableRow([])
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
        self.ServerDirectory=""  # Server directory to be created under /fanzines
        self.TargetDirectory=""     # Local directory containing LST files


    def Signature(self) -> int:        # FanzineTablePage(GridDataSource)
        s=self._colDefs.Signature()
        s+=hash(f"{self._name.strip()};{' '.join(self.TopComments).strip()};{' '.join(self.Locale).strip()}")
        s+=hash(f"{' '.join(self.TopComments).strip()};{' '.join(self.Locale).strip()}")
        s+=hash(f"{self.FanzineName};{self.Editors};{self.Dates};{self.FanzineType};{self.Credits};{self.Complete}{self.AlphabetizeIndividually}")
        s+=hash(f"{self.ServerDirectory.strip()};{self.TargetDirectory.strip()}")
        s+=sum([x.Signature()*(i+1) for i, x in enumerate(self._fanzineList)])
        return s+hash(self._specialTextColor)+self._colDefs.Signature()

    # Inherited from GridDataSource
    @property
    def Rows(self) -> list[FanzineIndexPageTableRow]:        # FanzineTablePage(GridDataSource)
        return self._fanzineList
    @Rows.setter
    def Rows(self, rows: list) -> None:        # FanzineTablePage(GridDataSource)
        self._fanzineList=rows

    @property
    def NumRows(self) -> int:        # FanzineTablePage(GridDataSource)
        return len(self._fanzineList)

    def __getitem__(self, index: int) -> FanzineIndexPageTableRow:        # FanzineTablePage(GridDataSource)
        return self.Rows[index]

    def __setitem__(self, index: int, val: FanzineIndexPageTableRow) -> None:        # FanzineTablePage(GridDataSource)
        self._fanzineList[index]=val


    @property
    def SpecialTextColor(self) -> Optional[Color]:        # FanzineTablePage(GridDataSource)
        return self._specialTextColor
    @SpecialTextColor.setter
    def SpecialTextColor(self, val: Optional[Color]) -> None:        # FanzineTablePage(GridDataSource)
        self._specialTextColor=val

    def CanAddColumns(self) -> bool:        # FanzineTablePage(GridDataSource)
        return True

    def InsertEmptyRows(self, insertat: int, num: int=1) -> None:        # FanzineTablePage(GridDataSource)
        for i in range(num):
            ftr=FanzineIndexPageTableRow([""]*self.NumCols)
            self._fanzineList.insert(insertat+i, ftr)

