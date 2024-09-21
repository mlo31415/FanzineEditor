# -*- coding: utf-8 -*-

###########################################################################
## Python code generated with wxFormBuilder (version 3.10.1-0-g8feb16b3)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc
import wx.grid

###########################################################################
## Class FanzineIndexPageEditGen
###########################################################################

class FanzineIndexPageEditGen ( wx.Dialog ):

	def __init__( self, parent ):
		wx.Dialog.__init__ ( self, parent, id = wx.ID_ANY, title = wx.EmptyString, pos = wx.DefaultPosition, size = wx.Size( 1126,3509 ), style = wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER )

		self.SetSizeHints( wx.DefaultSize, wx.DefaultSize )

		bSizer5 = wx.BoxSizer( wx.VERTICAL )

		self.m_toolBarTop = wx.ToolBar( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TB_HORIZONTAL )
		self.bAddNewIssues = wx.Button( self.m_toolBarTop, wx.ID_ANY, u"Add New Issue(s)", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_toolBarTop.AddControl( self.bAddNewIssues )
		self.m_EditFanzineName = wx.Button( self.m_toolBarTop, wx.ID_ANY, u"Edit Fanzine Name", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_toolBarTop.AddControl( self.m_EditFanzineName )
		self.m_staticText14 = wx.StaticText( self.m_toolBarTop, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_staticText14.Wrap( -1 )

		self.m_toolBarTop.AddControl( self.m_staticText14 )
		self.bUpload = wx.Button( self.m_toolBarTop, wx.ID_ANY, u"Upload", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_toolBarTop.AddControl( self.bUpload )
		self.bClose = wx.Button( self.m_toolBarTop, wx.ID_ANY, u"Close", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_toolBarTop.AddControl( self.bClose )
		self.m_toolBarTop.Realize()

		bSizer5.Add( self.m_toolBarTop, 0, wx.EXPAND, 5 )

		bSizerMain = wx.BoxSizer( wx.VERTICAL )

		fgSizer8 = wx.FlexGridSizer( 0, 3, 0, 0 )
		fgSizer8.SetFlexibleDirection( wx.BOTH )
		fgSizer8.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		fgSizer4 = wx.FlexGridSizer( 2, 4, 0, 0 )
		fgSizer4.SetFlexibleDirection( wx.BOTH )
		fgSizer4.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		self.m_staticText4 = wx.StaticText( self, wx.ID_ANY, u"Fanzine Name:", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_staticText4.Wrap( -1 )

		self.m_staticText4.SetMinSize( wx.Size( 200,-1 ) )
		self.m_staticText4.SetMaxSize( wx.Size( -1,50 ) )

		fgSizer4.Add( self.m_staticText4, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL|wx.FIXED_MINSIZE, 5 )

		self.tFanzineName = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.Size( 200,-1 ), 0 )
		self.tFanzineName.SetToolTip( u"The name of the fanzine serires." )
		self.tFanzineName.SetMinSize( wx.Size( 200,-1 ) )

		fgSizer4.Add( self.tFanzineName, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL|wx.FIXED_MINSIZE, 0 )

		self.m_staticText6 = wx.StaticText( self, wx.ID_ANY, u"Dates:", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_staticText6.Wrap( -1 )

		self.m_staticText6.SetMinSize( wx.Size( 200,-1 ) )
		self.m_staticText6.SetMaxSize( wx.Size( -1,50 ) )

		fgSizer4.Add( self.m_staticText6, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL|wx.FIXED_MINSIZE, 5 )

		self.tDates = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
		self.tDates.SetToolTip( u"The date range for this fanzine, years only. E.g., 1965-1974" )
		self.tDates.SetMinSize( wx.Size( 150,-1 ) )

		fgSizer4.Add( self.tDates, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT, 0 )

		self.cbComplete = wx.CheckBox( self, wx.ID_ANY, u"Complete", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.cbComplete.SetToolTip( u"Is this fanzine series complete on fanac.org?" )

		fgSizer4.Add( self.cbComplete, 0, wx.ALL, 5 )

		self.cbAlphabetizeIndividually = wx.CheckBox( self, wx.ID_ANY, u"Alphabetize Individually", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.cbAlphabetizeIndividually.SetToolTip( u"Do we want to treat the issues in this page as independent fanzines rather than issues of this page?" )

		fgSizer4.Add( self.cbAlphabetizeIndividually, 0, wx.ALL, 5 )


		fgSizer8.Add( fgSizer4, 0, wx.EXPAND, 5 )

		fgSizer91 = wx.FlexGridSizer( 0, 2, 0, 0 )
		fgSizer91.SetFlexibleDirection( wx.BOTH )
		fgSizer91.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		bSizer6 = wx.BoxSizer( wx.VERTICAL )

		fgSizer10 = wx.FlexGridSizer( 0, 2, 0, 0 )
		fgSizer10.SetFlexibleDirection( wx.BOTH )
		fgSizer10.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		self.m_staticText13 = wx.StaticText( self, wx.ID_ANY, u"Fanzine Type:   ", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_staticText13.Wrap( -1 )

		fgSizer10.Add( self.m_staticText13, 0, wx.ALL, 5 )

		tFanzineTypeChoices = [ u" ", u"Genzine", u"Apazine", u"Perzine", u"Newszine", u"Collection", u"Related", u"Clubzine", u"Adzine", u"Reference" ]
		self.tFanzineType = wx.Choice( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, tFanzineTypeChoices, 0 )
		self.tFanzineType.SetSelection( 0 )
		fgSizer10.Add( self.tFanzineType, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0 )


		bSizer6.Add( fgSizer10, 1, wx.EXPAND, 5 )

		self.tClubname = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
		self.tClubname.SetMinSize( wx.Size( 200,-1 ) )

		bSizer6.Add( self.tClubname, 0, wx.ALL, 5 )


		fgSizer91.Add( bSizer6, 1, wx.EXPAND, 5 )


		fgSizer8.Add( fgSizer91, 1, wx.EXPAND, 5 )

		fgSizer9 = wx.FlexGridSizer( 2, 2, 0, 0 )
		fgSizer9.SetFlexibleDirection( wx.BOTH )
		fgSizer9.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		self.m_staticText5 = wx.StaticText( self, wx.ID_ANY, u"          Editor(s): \n   (one per line) ", wx.Point( -1,-1 ), wx.DefaultSize, 0 )
		self.m_staticText5.Wrap( -1 )

		self.m_staticText5.SetMaxSize( wx.Size( -1,50 ) )

		fgSizer9.Add( self.m_staticText5, 0, wx.ALIGN_RIGHT|wx.ALIGN_TOP|wx.FIXED_MINSIZE, 5 )

		self.tEditors = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE )
		self.tEditors.SetToolTip( u"A list of editors separated by commans." )
		self.tEditors.SetMinSize( wx.Size( 300,80 ) )

		fgSizer9.Add( self.tEditors, 0, wx.ALIGN_TOP|wx.EXPAND, 5 )


		fgSizer8.Add( fgSizer9, 0, wx.EXPAND, 5 )


		bSizerMain.Add( fgSizer8, 0, wx.EXPAND, 5 )

		fgSizer6 = wx.FlexGridSizer( 1, 5, 0, 0 )
		fgSizer6.SetFlexibleDirection( wx.BOTH )
		fgSizer6.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		self.m_staticText38 = wx.StaticText( self, wx.ID_ANY, u"Server Directory:", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_staticText38.Wrap( -1 )

		fgSizer6.Add( self.m_staticText38, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, 5 )

		self.tServerDirectory = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
		self.tServerDirectory.SetMinSize( wx.Size( 250,-1 ) )

		fgSizer6.Add( self.tServerDirectory, 0, wx.ALL, 5 )

		self.m_bpButton1 = wx.BitmapButton( self, wx.ID_ANY, wx.NullBitmap, wx.DefaultPosition, wx.Size( 25,25 ), wx.BU_AUTODRAW|0 )
		self.m_bpButton1.SetForegroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_ACTIVECAPTION ) )
		self.m_bpButton1.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_ACTIVECAPTION ) )

		fgSizer6.Add( self.m_bpButton1, 0, wx.ALIGN_CENTER|wx.ALL, 5 )

		self.m_staticText39 = wx.StaticText( self, wx.ID_ANY, u"Local Directory:", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_staticText39.Wrap( -1 )

		fgSizer6.Add( self.m_staticText39, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, 5 )

		self.tLocalDirectory = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
		self.tLocalDirectory.SetMinSize( wx.Size( 180,-1 ) )

		fgSizer6.Add( self.tLocalDirectory, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT, 5 )


		bSizerMain.Add( fgSizer6, 0, wx.EXPAND, 5 )

		fgSizerComments = wx.FlexGridSizer( 4, 2, 0, 0 )
		fgSizerComments.AddGrowableCol( 1 )
		fgSizerComments.AddGrowableRow( 1 )
		fgSizerComments.SetFlexibleDirection( wx.BOTH )
		fgSizerComments.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		self.m_staticText2 = wx.StaticText( self, wx.ID_ANY, u"Top Comments: ", wx.Point( -1,-1 ), wx.DefaultSize, 0 )
		self.m_staticText2.Wrap( -1 )

		fgSizerComments.Add( self.m_staticText2, 1, wx.ALIGN_RIGHT|wx.ALL, 5 )

		self.tTopComments = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE )
		self.tTopComments.SetToolTip( u"Other top blather for the fanzine series page." )
		self.tTopComments.SetMinSize( wx.Size( -1,100 ) )

		fgSizerComments.Add( self.tTopComments, 1, wx.ALL|wx.EXPAND, 5 )

		self.m_staticText21 = wx.StaticText( self, wx.ID_ANY, u"Locale Info:", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_staticText21.Wrap( -1 )

		fgSizerComments.Add( self.m_staticText21, 0, wx.ALIGN_RIGHT|wx.ALL, 5 )

		self.tLocaleText = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE )
		self.tLocaleText.SetToolTip( u"The location for this fanzine: Country, Country: City, State: City" )
		self.tLocaleText.SetMinSize( wx.Size( -1,30 ) )
		self.tLocaleText.SetMaxSize( wx.Size( -1,30 ) )

		fgSizerComments.Add( self.tLocaleText, 0, wx.ALL|wx.EXPAND, 5 )

		self.m_staticText9 = wx.StaticText( self, wx.ID_ANY, u"Credits: ", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_staticText9.Wrap( -1 )

		fgSizerComments.Add( self.m_staticText9, 0, wx.ALIGN_RIGHT|wx.ALL, 5 )

		self.tCredits = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE )
		self.tCredits.SetToolTip( u"A free-form list of people who have contributed scans to this fanzine series." )
		self.tCredits.SetMinSize( wx.Size( -1,30 ) )
		self.tCredits.SetMaxSize( wx.Size( -1,30 ) )

		fgSizerComments.Add( self.tCredits, 0, wx.ALL|wx.EXPAND, 5 )


		bSizerMain.Add( fgSizerComments, 0, wx.ALL|wx.EXPAND, 5 )

		theIssueGrid = wx.BoxSizer( wx.VERTICAL )

		self.wxGrid = wx.grid.Grid( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0 )

		# Grid
		self.wxGrid.CreateGrid( 150, 15 )
		self.wxGrid.EnableEditing( True )
		self.wxGrid.EnableGridLines( True )
		self.wxGrid.EnableDragGridSize( False )
		self.wxGrid.SetMargins( 0, 0 )

		# Columns
		self.wxGrid.AutoSizeColumns()
		self.wxGrid.EnableDragColMove( True )
		self.wxGrid.EnableDragColSize( False )
		self.wxGrid.SetColLabelSize( 30 )
		self.wxGrid.SetColLabelAlignment( wx.ALIGN_CENTER, wx.ALIGN_CENTER )

		# Rows
		self.wxGrid.AutoSizeRows()
		self.wxGrid.EnableDragRowSize( True )
		self.wxGrid.SetRowLabelSize( 80 )
		self.wxGrid.SetRowLabelAlignment( wx.ALIGN_CENTER, wx.ALIGN_CENTER )

		# Label Appearance

		# Cell Defaults
		self.wxGrid.SetDefaultCellAlignment( wx.ALIGN_LEFT, wx.ALIGN_TOP )
		theIssueGrid.Add( self.wxGrid, 1, wx.ALL|wx.EXPAND, 5 )


		bSizerMain.Add( theIssueGrid, 1, wx.EXPAND, 5 )


		bSizer5.Add( bSizerMain, 0, wx.EXPAND, 5 )


		self.SetSizer( bSizer5 )
		self.Layout()
		self.m_GridPopup = wx.Menu()
		self.m_menuItemPopupCopy = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Copy", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupCopy )

		self.m_menuItemPopupPaste = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Paste", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupPaste )

		self.m_menuItemPopupEraseSelection = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Erase Selection", u"Erase (but do not delete) the selected cells.", wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupEraseSelection )

		self.m_menuItemPopupInsertText = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Insert a Text Line", u"Insert a new text line at the selected location.", wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupInsertText )

		self.m_menuItemPopupDelCol = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Delete Column", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupDelCol )

		self.m_menuItemClearAllLinks = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Clear All Links", u"Remove hyperlinks from selected row.", wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemClearAllLinks )

		self.m_menuItemPopupDelRow = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Delete Row(s)", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupDelRow )

		self.m_menuItemPopupInsertRow = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Insert a Row", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupInsertRow )

		self.m_menuItemPopupInsertColRight = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Insert Column to Right", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupInsertColRight )

		self.m_menuItemPopupInsertColLeft = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Insert Column to Left", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupInsertColLeft )

		self.m_menuItemPopupRenameCol = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Rename Column", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupRenameCol )

		self.m_menuItemPopupSortOnCol = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Sort on Selected Column", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupSortOnCol )

		self.m_menuItemPopupExtractScanner = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Extract Scanner", u"If ther Notes column contains information on who did the scanning, extract that information and add it to a Scanned By column, creating it if needed.", wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupExtractScanner )

		self.m_menuItemPopupTidyUpColumns = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Tidy Up Columns", u"Standardize columns:\n* Extract APA mailing info and add to a Milaings column\n* If there is a PDF column, fill it in with \"PDF\" as appropriate\n* Fill in the Pages column as apporpriate\n* Standardize column names", wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupTidyUpColumns )

		self.m_menuItemPopupExtractEditor = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Extract Editor", u"If ther Notes column contains information on the issue's editor, extract that information and add it to an Editors column, creating it if needed.", wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupExtractEditor )

		self.m_menuItemPopupPropagateEditor = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Propagate Editor", u"If there is an editors column and if editors have been specific for the whole run, replace all blank cells in the editors column with the series editors.", wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupPropagateEditor )

		self.m_menuItemPopupMergeRows = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Merge Adjacent Rows", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupMergeRows )

		self.m_menuItemPopupReplace = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Replace w/new PDF", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupReplace )

		self.m_menuItemPopupRenamePDF = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Rename PDF on Server", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemPopupRenamePDF )

		self.m_menuItemAllowEditing = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Allow Editing", wx.EmptyString, wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemAllowEditing )

		self.m_menuItemAddLink = wx.MenuItem( self.m_GridPopup, wx.ID_ANY, u"Add a Link", u"Add a link to the selected row.", wx.ITEM_NORMAL )
		self.m_GridPopup.Append( self.m_menuItemAddLink )

		self.Bind( wx.EVT_RIGHT_DOWN, self.FanzineIndexPageEditGenOnContextMenu )


		self.Centre( wx.BOTH )

		# Connect Events
		self.Bind( wx.EVT_CLOSE, self.OnClose )
		self.bAddNewIssues.Bind( wx.EVT_BUTTON, self.OnAddNewIssues )
		self.m_EditFanzineName.Bind( wx.EVT_BUTTON, self.OnEditFanzineNameClicked )
		self.bUpload.Bind( wx.EVT_BUTTON, self.OnUpload )
		self.bClose.Bind( wx.EVT_BUTTON, self.OnClose )
		self.tFanzineName.Bind( wx.EVT_CHAR, self.OnFanzineNameChar )
		self.tFanzineName.Bind( wx.EVT_TEXT, self.OnFanzineNameText )
		self.tDates.Bind( wx.EVT_TEXT, self.OnDatesText )
		self.cbComplete.Bind( wx.EVT_CHECKBOX, self.OnCheckComplete )
		self.cbAlphabetizeIndividually.Bind( wx.EVT_CHECKBOX, self.OnCheckAlphabetizeIndividually )
		self.tFanzineType.Bind( wx.EVT_CHOICE, self.OnFanzineTypeSelect )
		self.tClubname.Bind( wx.EVT_TEXT, self.OnClubname )
		self.tEditors.Bind( wx.EVT_TEXT, self.OnEditorsText )
		self.tServerDirectory.Bind( wx.EVT_CHAR, self.OnServerDirectoryChar )
		self.tServerDirectory.Bind( wx.EVT_TEXT, self.OnServerDirectoryText )
		self.m_bpButton1.Bind( wx.EVT_BUTTON, self.OnButtonClickCopyServerDir )
		self.tLocalDirectory.Bind( wx.EVT_CHAR, self.OnLocalDirectoryChar )
		self.tLocalDirectory.Bind( wx.EVT_TEXT, self.OnLocalDirectoryText )
		self.tTopComments.Bind( wx.EVT_TEXT, self.OnTopCommentsText )
		self.tLocaleText.Bind( wx.EVT_TEXT, self.OnLocaleText )
		self.tCredits.Bind( wx.EVT_TEXT, self.OnCreditsText )
		self.wxGrid.Bind( wx.grid.EVT_GRID_CELL_CHANGED, self.OnGridCellChanged )
		self.wxGrid.Bind( wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.OnGridCellLeftClick )
		self.wxGrid.Bind( wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.OnGridCellDoubleClick )
		self.wxGrid.Bind( wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.OnGridCellRightClick )
		self.wxGrid.Bind( wx.grid.EVT_GRID_EDITOR_SHOWN, self.OnGridEditorShown )
		self.wxGrid.Bind( wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.OnGridLabelLeftClick )
		self.wxGrid.Bind( wx.grid.EVT_GRID_LABEL_RIGHT_CLICK, self.OnGridLabelRightClick )
		self.wxGrid.Bind( wx.EVT_KEY_DOWN, self.OnKeyDown )
		self.wxGrid.Bind( wx.EVT_KEY_UP, self.OnKeyUp )
		self.wxGrid.Bind( wx.EVT_LEFT_DOWN, self.OnGridCellLeftDown )
		self.Bind( wx.EVT_MENU, self.OnPopupCopy, id = self.m_menuItemPopupCopy.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupPaste, id = self.m_menuItemPopupPaste.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupEraseSelection, id = self.m_menuItemPopupEraseSelection.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupInsertText, id = self.m_menuItemPopupInsertText.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupDelCol, id = self.m_menuItemPopupDelCol.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupClearAllLinks, id = self.m_menuItemClearAllLinks.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupDelRow, id = self.m_menuItemPopupDelRow.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupInsertRow, id = self.m_menuItemPopupInsertRow.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupInsertColRight, id = self.m_menuItemPopupInsertColRight.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupInsertColLeft, id = self.m_menuItemPopupInsertColLeft.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupRenameCol, id = self.m_menuItemPopupRenameCol.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupSortOnSelectedColumn, id = self.m_menuItemPopupSortOnCol.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupExtractScanner, id = self.m_menuItemPopupExtractScanner.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupTidyUpColumns, id = self.m_menuItemPopupTidyUpColumns.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupExtractEditor, id = self.m_menuItemPopupExtractEditor.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupPropagateEditor, id = self.m_menuItemPopupPropagateEditor.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupMergeRows, id = self.m_menuItemPopupMergeRows.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupReplace, id = self.m_menuItemPopupReplace.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupRenamePDF, id = self.m_menuItemPopupRenamePDF.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupAllowEditing, id = self.m_menuItemAllowEditing.GetId() )
		self.Bind( wx.EVT_MENU, self.OnPopupAddLink, id = self.m_menuItemAddLink.GetId() )

	def __del__( self ):
		pass


	# Virtual event handlers, override them in your derived class
	def OnClose( self, event ):
		event.Skip()

	def OnAddNewIssues( self, event ):
		event.Skip()

	def OnEditFanzineNameClicked( self, event ):
		event.Skip()

	def OnUpload( self, event ):
		event.Skip()


	def OnFanzineNameChar( self, event ):
		event.Skip()

	def OnFanzineNameText( self, event ):
		event.Skip()

	def OnDatesText( self, event ):
		event.Skip()

	def OnCheckComplete( self, event ):
		event.Skip()

	def OnCheckAlphabetizeIndividually( self, event ):
		event.Skip()

	def OnFanzineTypeSelect( self, event ):
		event.Skip()

	def OnClubname( self, event ):
		event.Skip()

	def OnEditorsText( self, event ):
		event.Skip()

	def OnServerDirectoryChar( self, event ):
		event.Skip()

	def OnServerDirectoryText( self, event ):
		event.Skip()

	def OnButtonClickCopyServerDir( self, event ):
		event.Skip()

	def OnLocalDirectoryChar( self, event ):
		event.Skip()

	def OnLocalDirectoryText( self, event ):
		event.Skip()

	def OnTopCommentsText( self, event ):
		event.Skip()

	def OnLocaleText( self, event ):
		event.Skip()

	def OnCreditsText( self, event ):
		event.Skip()

	def OnGridCellChanged( self, event ):
		event.Skip()

	def OnGridCellLeftClick( self, event ):
		event.Skip()

	def OnGridCellDoubleClick( self, event ):
		event.Skip()

	def OnGridCellRightClick( self, event ):
		event.Skip()

	def OnGridEditorShown( self, event ):
		event.Skip()

	def OnGridLabelLeftClick( self, event ):
		event.Skip()

	def OnGridLabelRightClick( self, event ):
		event.Skip()

	def OnKeyDown( self, event ):
		event.Skip()

	def OnKeyUp( self, event ):
		event.Skip()

	def OnGridCellLeftDown( self, event ):
		event.Skip()

	def OnPopupCopy( self, event ):
		event.Skip()

	def OnPopupPaste( self, event ):
		event.Skip()

	def OnPopupEraseSelection( self, event ):
		event.Skip()

	def OnPopupInsertText( self, event ):
		event.Skip()

	def OnPopupDelCol( self, event ):
		event.Skip()

	def OnPopupClearAllLinks( self, event ):
		event.Skip()

	def OnPopupDelRow( self, event ):
		event.Skip()

	def OnPopupInsertRow( self, event ):
		event.Skip()

	def OnPopupInsertColRight( self, event ):
		event.Skip()

	def OnPopupInsertColLeft( self, event ):
		event.Skip()

	def OnPopupRenameCol( self, event ):
		event.Skip()

	def OnPopupSortOnSelectedColumn( self, event ):
		event.Skip()

	def OnPopupExtractScanner( self, event ):
		event.Skip()

	def OnPopupTidyUpColumns( self, event ):
		event.Skip()

	def OnPopupExtractEditor( self, event ):
		event.Skip()

	def OnPopupPropagateEditor( self, event ):
		event.Skip()

	def OnPopupMergeRows( self, event ):
		event.Skip()

	def OnPopupReplace( self, event ):
		event.Skip()

	def OnPopupRenamePDF( self, event ):
		event.Skip()

	def OnPopupAllowEditing( self, event ):
		event.Skip()

	def OnPopupAddLink( self, event ):
		event.Skip()

	def FanzineIndexPageEditGenOnContextMenu( self, event ):
		self.PopupMenu( self.m_GridPopup, event.GetPosition() )


###########################################################################
## Class FanzinesGridGen
###########################################################################

class FanzinesGridGen ( wx.Frame ):

	def __init__( self, parent ):
		wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = u"Fanzines Editor", pos = wx.DefaultPosition, size = wx.Size( 1037,502 ), style = wx.DEFAULT_FRAME_STYLE|wx.RESIZE_BORDER|wx.TAB_TRAVERSAL )

		self.SetSizeHints( wx.DefaultSize, wx.DefaultSize )

		bSizer3 = wx.BoxSizer( wx.VERTICAL )

		fgSizer7 = wx.FlexGridSizer( 6, 1, 0, 0 )
		fgSizer7.SetFlexibleDirection( wx.BOTH )
		fgSizer7.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )


		fgSizer7.Add( ( 0, 12), 1, wx.EXPAND, 5 )

		fgSizer71 = wx.FlexGridSizer( 0, 5, 0, 0 )
		fgSizer71.SetFlexibleDirection( wx.BOTH )
		fgSizer71.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		self.m_staticText12 = wx.StaticText( self, wx.ID_ANY, u"    Search: ", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_staticText12.Wrap( -1 )

		self.m_staticText12.SetFont( wx.Font( 14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, False, "Arial" ) )

		fgSizer71.Add( self.m_staticText12, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		self.tSearch = wx.TextCtrl( self, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
		self.tSearch.SetFont( wx.Font( 14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, False, wx.EmptyString ) )
		self.tSearch.SetMinSize( wx.Size( 170,30 ) )

		fgSizer71.Add( self.tSearch, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		self.bClearSearch = wx.Button( self, wx.ID_ANY, u"X", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.bClearSearch.SetFont( wx.Font( wx.NORMAL_FONT.GetPointSize(), wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, False, wx.EmptyString ) )
		self.bClearSearch.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_WINDOW ) )
		self.bClearSearch.SetMaxSize( wx.Size( 20,20 ) )

		fgSizer71.Add( self.bClearSearch, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )


		fgSizer7.Add( fgSizer71, 0, wx.EXPAND, 5 )


		fgSizer7.Add( ( 0, 12), 1, wx.EXPAND, 5 )

		fgSizer8 = wx.FlexGridSizer( 0, 4, 0, 0 )
		fgSizer8.SetFlexibleDirection( wx.BOTH )
		fgSizer8.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )

		self.bExit = wx.Button( self, wx.ID_ANY, u"Exit", wx.DefaultPosition, wx.DefaultSize, 0 )
		fgSizer8.Add( self.bExit, 0, wx.ALL, 5 )

		self.bUpload = wx.Button( self, wx.ID_ANY, u"Upload", wx.DefaultPosition, wx.DefaultSize, 0 )
		fgSizer8.Add( self.bUpload, 0, wx.ALL, 5 )

		self.bAddNewFanzine = wx.Button( self, wx.ID_ANY, u"Add New Fanzine", wx.DefaultPosition, wx.DefaultSize, 0 )
		fgSizer8.Add( self.bAddNewFanzine, 0, wx.ALL, 5 )

		self.bDeleteFanzine = wx.Button( self, wx.ID_ANY, u"Delete Fanzine", wx.DefaultPosition, wx.DefaultSize, 0 )
		fgSizer8.Add( self.bDeleteFanzine, 0, wx.ALL, 5 )


		fgSizer7.Add( fgSizer8, 1, wx.EXPAND, 5 )

		sbSizer5 = wx.StaticBoxSizer( wx.StaticBox( self, wx.ID_ANY, u"Classic Fanzines line information:" ), wx.VERTICAL )

		self.CFLText = wx.StaticText( sbSizer5.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
		self.CFLText.Wrap( -1 )

		self.CFLText.SetBackgroundColour( wx.Colour( 255, 255, 255 ) )
		self.CFLText.SetMinSize( wx.Size( 900,40 ) )

		sbSizer5.Add( self.CFLText, 0, wx.ALL, 5 )


		fgSizer7.Add( sbSizer5, 1, wx.EXPAND, 5 )


		bSizer3.Add( fgSizer7, 0, wx.EXPAND, 5 )

		self.wxGrid = wx.grid.Grid( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0 )

		# Grid
		self.wxGrid.CreateGrid( 10, 5 )
		self.wxGrid.EnableEditing( False )
		self.wxGrid.EnableGridLines( True )
		self.wxGrid.EnableDragGridSize( False )
		self.wxGrid.SetMargins( 0, 0 )

		# Columns
		self.wxGrid.EnableDragColMove( False )
		self.wxGrid.EnableDragColSize( True )
		self.wxGrid.SetColLabelAlignment( wx.ALIGN_CENTER, wx.ALIGN_CENTER )

		# Rows
		self.wxGrid.EnableDragRowSize( True )
		self.wxGrid.SetRowLabelAlignment( wx.ALIGN_CENTER, wx.ALIGN_CENTER )

		# Label Appearance

		# Cell Defaults
		self.wxGrid.SetDefaultCellAlignment( wx.ALIGN_LEFT, wx.ALIGN_TOP )
		bSizer3.Add( self.wxGrid, 0, wx.ALL, 5 )


		self.SetSizer( bSizer3 )
		self.Layout()

		self.Centre( wx.BOTH )

		# Connect Events
		self.Bind( wx.EVT_CLOSE, self.OnClosePressed )
		self.tSearch.Bind( wx.EVT_CHAR, self.OnSearchTextChar )
		self.tSearch.Bind( wx.EVT_TEXT, self.OnSearchText )
		self.bClearSearch.Bind( wx.EVT_BUTTON, self.OnClearSearch )
		self.bExit.Bind( wx.EVT_BUTTON, self.OnExitPressed )
		self.bUpload.Bind( wx.EVT_BUTTON, self.OnUploadPressed )
		self.bAddNewFanzine.Bind( wx.EVT_BUTTON, self.OnAddNewFanzine )
		self.bDeleteFanzine.Bind( wx.EVT_BUTTON, self.OnDeleteFanzineClicked )
		self.wxGrid.Bind( wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.OnGridCellLeftClick )
		self.wxGrid.Bind( wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.OnGridCellDoubleClick )
		self.wxGrid.Bind( wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.OnGridCellRightClick )

	def __del__( self ):
		pass


	# Virtual event handlers, override them in your derived class
	def OnClosePressed( self, event ):
		event.Skip()

	def OnSearchTextChar( self, event ):
		event.Skip()

	def OnSearchText( self, event ):
		event.Skip()

	def OnClearSearch( self, event ):
		event.Skip()

	def OnExitPressed( self, event ):
		event.Skip()

	def OnUploadPressed( self, event ):
		event.Skip()

	def OnAddNewFanzine( self, event ):
		event.Skip()

	def OnDeleteFanzineClicked( self, event ):
		event.Skip()

	def OnGridCellLeftClick( self, event ):
		event.Skip()

	def OnGridCellDoubleClick( self, event ):
		event.Skip()

	def OnGridCellRightClick( self, event ):
		event.Skip()


