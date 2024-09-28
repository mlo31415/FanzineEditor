from __future__ import annotations
import re
from datetime import datetime

from unidecode import unidecode

from HelpersPackage import SortPersonsName, Int0, FindNextBracketedText, SplitOnSpansOfLineBreaks
from FanzineIssueSpecPackage import FanzineDate

########################################################################
# A class to hold the updated date in standard ConEditor format
class ClassicFanzinesDate:
    def __init__(self, val: datetime|str|ClassicFanzinesDate|None=None):
        self._date: datetime|str|ClassicFanzinesDate|None=None
        self.Set(val)       # The date is stored as a datetime


    def __eq__(self, other) -> bool:
        if not isinstance(other, ClassicFanzinesDate):
            other=ClassicFanzinesDate(other)
        return self._date == other._date

    def __hash__(self) -> int:
        return self._date.__hash__()

    @property
    def Date(self) -> datetime:
        if self._date is None:
            return datetime(1900, 1, 1)
        return self._date
    @Date.setter
    def Date(self, val: datetime|str|None):
        self.Set(val)

    # Turn any input value into the proper internal format
    def Set(self, val: datetime|str|None) -> None:
        if val is None:
            self._date=None
            return

        if isinstance(val, datetime):
            self._date=val
            return

        if isinstance(val, ClassicFanzinesDate):
            self._date=val.Date
            return

        if isinstance(val, str):    # Required format: 'September 27, 1977' or empty string
            if val == "":
                self._date=None
                return
            if val.lower() == "long, long ago":
                self.Set("1900-01-01")
                return

            try:
                self._date=datetime.strptime(val, "%Y-%m-%d")
            except ValueError:
                try:
                    self._date=datetime.strptime(val, '%B %d, %Y')
                except ValueError:
                    # In desperation, try FanzineDate's general date matcher
                    self._date=FanzineDate().Match(val).DateTime
            return
        assert False


    def __str__(self) -> str:
        if self._date is None or self._date == "":
            return ""
        return f"{self._date:%B %d, %Y}"

    # This is defined so that we can get the same time format in the Now string as we do in the __str__
    def Now(self) -> str:
        return f"{datetime.now():%B %d, %Y}"


    def DaysAgo(self) -> int|None:
        if self._date is None:
            return None
        return (datetime.now()-self._date).days


#==========================================================================================================
# A class to hold the information in a single line of the Classic Fanzines page
class ClassicFanzinesLine:

    def __init__(self, cfl=None):
        # OCreate empty CFL
        self._displayName: str=""
        self._url: str=""
        self._otherNames: list[str]=[]
        self._editors: str=""
        self._dates: str=""
        self._type: str=""
        self._clubname: str=""
        self._issues: str=""
        self._topcomments: str=""
        self._country: str=""
        self._complete: bool=False
        self._betterScanNeeded: bool=False
        self._created: ClassicFanzinesDate|None=None
        self._updated: ClassicFanzinesDate|None=None
        self.DuplicateCopy=False

        # Initialize from another CFL by deep copying
        if isinstance(cfl, ClassicFanzinesLine):
            self._displayName=cfl._displayName
            self._url=cfl._url
            self._otherNames=cfl._otherNames       # Alternate names for this fanzine
            self._editors=cfl._editors
            self._dates=cfl._dates
            self._type=cfl._type
            self._clubname=cfl._clubname
            self._issues=cfl._issues
            self._topcomments=cfl._topcomments
            self._country=cfl._country
            self._complete=cfl._complete
            self._betterScanNeeded=cfl._betterScanNeeded
            self._created=cfl._created
            self._updated=cfl._updated
            self.DuplicateCopy=cfl.DuplicateCopy
            return



    def __str__(self) -> str:
        s=f"{self.DisplayName}  [{self.DisplayNameSort}]     {self._editors}  [{self.EditorsSort}]     {self._dates}  [{self.DatesSort}]     "
        s+=f"{self._issues} issues    Type={self.Type}     \nFlags: {'(Complete)' if self._complete else ''}      Created={self.Created}       Updated={self.Updated} "
        return s

    def __eq__(self, other) -> bool:
        if not isinstance(other, ClassicFanzinesLine):
            return False

        return self._displayName == other._displayName and \
            self._url == other._url and \
            self._otherNames == other._otherNames and \
            self._editors == other._editors and \
            self._dates == other._dates and \
            self._type == other._type and \
            self._clubname == other._clubname and \
            self._issues == other._issues and \
            self._topcomments == other._topcomments and \
            self._country == other._country and \
            self._complete == other._complete and \
            self._betterScanNeeded == other._betterScanNeeded  and \
            self._updated == other._updated and \
            self._created == other._created


    def __hash__(self) -> int:
        return hash(self._displayName) + \
            hash(self._url) + \
            hash(".".join(self._otherNames)) + \
            hash(self._editors) + \
            hash(self._dates) + \
            hash(self._type) + \
            hash(self._clubname)+ \
            hash(self._issues) + \
            hash(self._topcomments) + \
            hash(self._country) + \
            hash(self._complete) + \
            hash(self._betterScanNeeded) + \
            hash(self._created) + \
            hash(self._updated)


    def Deepcopy(self) -> ClassicFanzinesLine:
        cfl=ClassicFanzinesLine()
        cfl._displayName=self._displayName
        cfl._url=self._url
        cfl._otherNames=[]
        for on in self._otherNames:
            cfl._otherNames.append(on)
        cfl._editors=self._editors
        cfl._dates=self._dates
        cfl._type=self._type
        cfl._clubname=self._clubname
        cfl._issues=self._issues
        cfl._topcomments=self._topcomments
        cfl._country=self._country
        cfl._complete=self._complete
        cfl._betterScanNeeded=self._betterScanNeeded
        cfl._created=self._created
        cfl._updated=self._updated
        return cfl


    @property
    def DisplayName(self) -> str:
        return self._displayName
    @DisplayName.setter
    def DisplayName(self, val: str):
        self._displayName=val

    @property
    def DisplayNameSort(self) -> str:
        pre, _, mid, post=FindNextBracketedText(self.DisplayName)
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
    def OtherNames(self) -> [str]:
        return self._otherNames
    @OtherNames.setter
    def OtherNames(self, val: str|list[str]):
        if isinstance(val, list):
            self._otherNames=val
            return
        self._otherNames=SplitOnSpansOfLineBreaks(val)

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
        ed=unidecode(eds[0])
        return SortPersonsName(ed).casefold()
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
    def Clubname(self) -> str:
        return self._clubname
    @Clubname.setter
    def Clubname(self, val: str):
        self._clubname=val

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
    def TopComments(self) -> str:
        return self._topcomments
    @TopComments.setter
    def TopComments(self, val: str):
        self._topcomments=val

    @property
    def Country(self) -> str:
        return self._country
    @Country.setter
    def Country(self, val: str):
        self._country=val

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
    def Created(self) -> ClassicFanzinesDate:
        if self._created is None:
            return ClassicFanzinesDate("1900-01-01")        # "Empty" date
        return self._created
    @Created.setter
    def Created(self, val: ClassicFanzinesDate):
        self._created=ClassicFanzinesDate(val)

    @property
    def Updated(self) -> ClassicFanzinesDate:
        if self._updated is None:
            return ClassicFanzinesDate("1900-01-01")        # "Empty" date
        return self._updated
    @Updated.setter
    def Updated(self, val: ClassicFanzinesDate):
        self._updated=ClassicFanzinesDate(val)

