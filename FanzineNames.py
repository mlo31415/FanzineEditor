import re

from HelpersPackage import SplitOnSpansOfLineBreaks, RemoveLinebreaks

from Log import Log

class FanzineNames:
    def __init__(self, name: str="", othernames: list[str]|None=None):
        self._mainname: str=""
        self._othernames: list[str]=[]

        self.MainName=name  # Want to use the processing in the property

        if othernames is None:
            return

        if isinstance(othernames, list):
            self.Othernames=othernames
            return
        if isinstance(othernames, str):
            othernames=RemoveLinebreaks(othernames, replacement="<br>")
            if ("<br>" in othernames):
                self.Othernames=othernames.split("<br>")
            else:
                self.Othernames=othernames.split(",")


    def __hash__(self):
        return hash(self._mainname)+sum([hash(x) for x in self._othernames])

    def __eq__(self, other) -> bool:
        return self._mainname == other._mainname and all([x == y for x, y in zip(self._othernames, other._othernames)])

    def __str__(self):
        otherstuff=""
        if len(self._othernames) > 0:
            otherstuff=" / "+self.OthernamesAsStr(", ")
        return self._mainname+otherstuff


    def DeepCopy(self) -> "FanzineNames":
        fn=FanzineNames()
        fn._mainname=self._mainname
        fn._othernames=[x for x in self._othernames]
        return fn


    @property
    def MainName(self) -> str:
        return self._mainname
    @MainName.setter
    def MainName(self, val: str):
        self._mainname = RemoveLinebreaks(val)

    @property
    def Othernames(self) -> list[str]:
        return self._othernames
    @Othernames.setter
    def Othernames(self, val: list[str]):
        self._othernames=[y for y in [RemoveLinebreaks(x).strip() for x in val] if len(y) > 0]

    @property
    def OthernamesAsHTML(self) -> str:
        return self.OthernamesAsStr("<br>")
    @OthernamesAsHTML.setter
    def OthernamesAsHTML(self, val: str):
        fanzinename=SplitOnSpansOfLineBreaks(val)
        if len(fanzinename) > 1:
            self._othernames=fanzinename[1:]
        else:
            self._othernames=[]
        self._othernames=[x.strip() for x in self._othernames]


    def OthernamesAsStr(self, delim: str) -> str:
        return delim.join(self._othernames)


    def IntepretNewHeader(self, header: str) -> bool:
        # '<a href="https://fancyclopedia.org/ALW_Gazet">ALW Gazet</a> , Antwerpse Letterkundige and Wetenschappelijke Gazet'
        m=re.match(r"<a href=[\'\"]https?://fancyclopedia.org/(.*?)[\'\"]>(.*?)</a>(.*)$", header)
        if m is None:
            return False
        self.MainName=m.group(2)
        # Othernames can have commas and spaces around it, so split on them and strip them and drop any empty strings
        othernames=SplitOnSpansOfLineBreaks(m.group(3))
        self.Othernames=othernames
        return True


    def IntepretOldHeader(self, header: str) -> bool:
        # '<a href="https://fancyclopedia.org/ALW_Gazet">ALW Gazet</a> , Antwerpse Letterkundige and Wetenschappelijke Gazet'
        m=re.match(r"<td[^>]*><h1[^>]*>(.*)$", header, flags=re.IGNORECASE)
        if m is None:
            Log(f"IntepretOldHeader('{header}') failed")
            return False
        names=SplitOnSpansOfLineBreaks(m.group(1))
        self.MainName=names[0]
        self.Othernames=names[1:]
        return True


    def SwapMainNameAndOtherName(self, index: int) -> bool:
        if index > len(self._othernames)-1:
            return False
        mainname=self._mainname
        othername=self._othernames[index]
        self.MainName=othername
        self.Othernames[index]=mainname
        return True
