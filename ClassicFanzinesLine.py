#==========================================================================================================
# A class to holdthe information in a single like of the classic Fanzines page
class ClassicFanzinesLine:
    def __init__(self, clf=None):
        # Initialize from another CLF by deep copying
        if type(clf) is ClassicFanzinesLine:
            self._displayName: str=clf._displayName
            self._url: str=clf._url
            self._otherNames: str=clf._otherNames
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
    def URL(self) -> str:
        return self._url
