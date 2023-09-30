#==========================================================================================================
# A class to holdthe information in a single like of the classic Fanzines page
class ClassicFanzinesLine:
    def __init__(self, clf=None):
        # Initialize from another CLF by deep copying
        if type(clf) is ClassicFanzinesLine:
            self._displayName: str=clf._displayName
            self._url: str=clf._url
            self._otherNames: str=clf._otherNames       # Alternate names for this fanzine
            self._displayNameSort: str=clf._displayNameSort
            self._editors: str=clf._editors
            self._editorsSort: str=clf._editorsSort
            self._dates: str=clf._dates
            self._datesSort: str=clf._datesSort
            self._type: str=clf._type
            self._issues: str=clf._issues
            self._issuesSort: str=clf._issuesSort
            self._flag: str=clf._flag
            self._flagSort: str=clf._flagSort
            return

        # Otherwise, just fill it with empty strings
        self._displayName: str=""
        self._url: str=""
        self._otherNames: str=""
        self._displayNameSort: str=""
        self._editors: str=""
        self._editorsSort: str=""
        self._dates: str=""
        self._datesSort: str=""
        self._type: str=""
        self._issues: str=""
        self._issuesSort: str=""
        self._flag: str=""
        self._flagSort: str=""



    @property
    def DisplayName(self) -> str:
        return self._displayName
    @DisplayName.setter
    def DisplayName(self, val: str):
        self._displayName=val

    @property
    def URL(self) -> str:
        return self._url
    @URL.setter
    def URL(self, val: str):
        self._url=val

    @property
    def OtherNames(self) -> str:
        return self._otherNames
    @OtherNames.setter
    def OtherNames(self, val: str):
        self._otherNames=val

    @property
    def DisplayNameSort(self) -> str:
        return self._displayNameSort
    @DisplayNameSort.setter
    def DisplayNameSort(self, val: str):
        self._displayNameSort=val

    @property
    def Editors(self) -> str:
        return self._editors
    @Editors.setter
    def Editors(self, val: str):
        self._editors=val

    @property
    def EditorsSort(self) -> str:
        return self._editorsSort
    @EditorsSort.setter
    def EditorsSort(self, val: str):
        self._editorsSort=val

    @property
    def Dates(self) -> str:
        return self._dates
    @Dates.setter
    def Dates(self, val: str):
        self._dates=val

    @property
    def DatesSort(self) -> str:
        return self._datesSort
    @DatesSort.setter
    def DatesSort(self, val: str):
        self._datesSort=val

    @property
    def Type(self) -> str:
        return self._type
    @Type.setter
    def Type(self, val: str):
        self._type=val

    @property
    def Issues(self) -> str:
        return self._issues
    @Issues.setter
    def Issues(self, val: str):
        self._issues=val

    @property
    def IssuesSort(self) -> str:
        return self._issuesSort
    @IssuesSort.setter
    def IssuesSort(self, val: str):
        self._issuesSort=val

    @property
    def Flag(self) -> str:
        return self._flag
    @Flag.setter
    def Flag(self, val: str):
        self._flag=val

    @property
    def FlagSort(self) -> str:
        return self._flagSort
    @FlagSort.setter
    def FlagSort(self, val: str):
        self._flagSort=val

