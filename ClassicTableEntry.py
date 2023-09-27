from GenGUIClass import ClassicTableEntryDialogGen
from ClassicFanzinesLine import ClassicFanzinesLine

from wx._core import wxAssertionError
from wx import ID_CANCEL, ID_OK
from Log import Log

class ClassicTableEntryDlg(ClassicTableEntryDialogGen):
    def __init__(self, parent, clf: ClassicFanzinesLine):
        ClassicTableEntryDialogGen.__init__(self, parent)

        self._clf=clf

        self.tDisplayName.SetValue(self._clf.DisplayName)
        self.tDisplayNameSort.SetValue((self._clf.DisplayNameSort))
        self.tURL.SetValue(self._clf.URL)
        self.tOtherNames.SetValue(self._clf.OtherNames)
        self.tEditors.SetValue(self._clf.Editors)
        self.tEditorsSort.SetValue(self._clf.EditorsSort)
        self.tDates.SetValue(self._clf.Dates)
        self.tDatesSort.SetValue(self._clf.DatesSort)
        self.tType.SetValue(self._clf.Type)
        self.tIssues.SetValue(self._clf.Issues)
        self.tIssuesSort.SetValue(self._clf.IssuesSort)
        self.tFlags.SetValue(self._clf.Flag)
        self.tFlagsSort.SetValue(self._clf.FlagSort)

        self.Show(True)

    def OnCancel(self, event):
        self.EndModal(ID_CANCEL)

    def OnOK(self, event):
        self.EndModal(ID_OK)


    def OnTextDisplayName(self, event):
        self._clf._displayName=self.tDisplayName.GetValue()
        return

    def OnTextDisplayNameSort(self, event):
        self._clf._displayNameSort=self.tDisplayNameSort.GetValue()
        return

    def OnTextURL(self, event):
        self._clf._url=self.tURL.GetValue()
        return

    def OnTextOtherNames(self, event):
        self._clf._otherNames=self.tOtherNames.GetValue()
        return

    def OnTextEditors(self, event):
        self._clf._editors=self.tEditors.GetValue()
        return

    def OnTextEditorsSort(self, event):
        self._clf._editorsSort=self.tEditorsSort.GetValue()
        return

    def OnTextDates(self, event):
        self._clf._dates=self.tDates.GetValue()
        return

    def OnTextDatesSort(self, event):
        self._clf._datesSort=self.tDatesSort.GetValue()
        return

    def OnTextType(self, event):
        self._clf._type=self.tType.GetValue()
        return

    def OnTextIssues(self, event):
        self._clf._issues=self.tIssues.GetValue()
        return

    def OnTextIssuesSort(self, event):
        self._clf._issuesSort=self.tIssuesSort.GetValue()
        return

    def OnTextFlags(self, event):
        self._clf._flag=self.tFlags.GetValue()
        return

    def OnTextFlagsSort(self, event):
        self._clf._flagSort=self.tFlagsSort.GetValue()
        return