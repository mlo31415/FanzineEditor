import re
from datetime import datetime

from unidecode import unidecode

from HelpersPackage import SortPersonsName, Int0, FindAnyBracketedText
from FanzineIssueSpecPackage import FanzineDate

########################################################################
# A class to hold the updated date in standard ConEditor format
class Updated:
    def __init__(self, val: datetime|str|None=None):
        self._updated=self.Set(val)


    @property
    def Updated(self) -> datetime:
        if self._updated is None:
            return datetime(1900, 1, 1)
        return self._updated
    @Updated.setter
    def Updated(self, val: datetime|str|None) -> None:
        self._updated=self.Set(val)

    # Turn any input value into the proper internal format
    def Set(self, val: datetime|str|None) -> datetime|None:
        if type(val) is datetime:
            return val
        if val is None:
            return None
        if type(val) is str:    # Required format: 'September 27, 1977' or empty string
            if val == "":
                return None
            else:
                try:
                    return datetime.strptime(val, '%B %d, %Y')
                except ValueError:
                    # In desperation, try FanzineDate's general date matcher
                    return FanzineDate().Match(val).DateTime
        assert False


    def __str__(self) -> str:
        if self._updated is None or self._updated == "":
            return ""
        return f"{self._updated:%B %d, %Y}"


    def Now(self) -> str:
        return f"{datetime.now():%B %d, %Y}"

    # Has this been updated recently?
    @property
    def Recent(self) -> bool:
        return self._updated is not None and (datetime.now()-self._updated).days < 100


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
            self._complete: bool=clf._complete
            self._lastupdate: datetime=clf._lastupdate
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
        self._complete=False
        self._lastupdate=None



    @property
    def DisplayName(self) -> str:
        return self._displayName
    @DisplayName.setter
    def DisplayName(self, val: str):
        self._displayName=val

    @property
    def DisplayNameSort(self) -> str:
        pre, _, mid, post=FindAnyBracketedText(self.DisplayName)
        return unidecode(f"{pre} {mid} {post}".strip().casefold())
    @DisplayNameSort.setter
    def DisplayNameSort(self, val: str):
        assert False

    @property
    def ServerDir(self) -> str:
        return self._url
    @ServerDir.setter
    def ServerDir(self, val: str):
        self._url=val

    @property
    def OtherNames(self) -> str:
        return self._otherNames
    @OtherNames.setter
    def OtherNames(self, val: str):
        self._otherNames=val

    @property
    def Editors(self) -> str:
        return self._editors
    @Editors.setter
    def Editors(self, val: str):
        self._editors=val

    @property
    def EditorsSort(self) -> str:
        eds=re.split(r"<br/?>|,", self.Editors)
        # Sort based on the 1st editor's last name all caps.
        ed=unidecode(eds[0].casefold())
        return SortPersonsName(ed)
    @EditorsSort.setter
    def EditorsSort(self, val: str):
        assert False

    @property
    def Dates(self) -> str:
        return self._dates
    @Dates.setter
    def Dates(self, val: str):
        self._dates=val

    @property
    def DatesSort(self) -> str:
        # Sort based on 1st 4-digit year.  We need to find the year, as sometimes odd stuff gets entered!
        m=re.search(r"((?:19|20)[0-9][0-9])", self.Dates, 1)
        if m is None:
            # Can't find a fulll year.  Try replacing "?" with "0"
            d=self.Dates.replace("?", "0")
            m=re.search(r"((?:19|20)[0-9][0-9])", d, 1)
            if m is None:
                return "zzzz"
        return (m.groups()[0]+"0000")[0:4]
    @DatesSort.setter
    def DatesSort(self, val: str):
        assert False

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
        return f"{Int0(self.Issues):0{5}}"
    @IssuesSort.setter
    def IssuesSort(self, val: str):
        assert False

    @property
    def Flag(self) -> str:
        if self.Complete:
            return "Complete"
        return self._flag
    @Flag.setter
    def Flag(self, val: str):
        self._flag=val

    @property
    def Complete(self) -> bool:
        return self._complete
    @Complete.setter
    def Complete(self, val: bool):
        self._complete=val

    @property
    def LastUpdate(self) -> Updated:
        return self._lastupdate
    @LastUpdate.setter
    def LastUpdate(self, val: Updated|datetime):
        if type(val) is datetime:
            val=Updated(val)
        self._lastupdate=val

    @property
    # Has this fanzine been updated recently enough to be flagged?
    def UpdatedFlag(self) -> bool:
        return self.LastUpdate is not None and self.LastUpdate.Recent