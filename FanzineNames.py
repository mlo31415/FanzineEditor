import re

from HelpersPackage import SplitOnSpansOfLineBreaks

from Log import Log

class FanzineNames:
    def __init__(self, name: str="", othernames: list[str]|None=None):
        self._name=name

        if othernames is None or othernames == "":
            othernames=[]

        if isinstance(othernames, list):
            self._othernames=othernames
        elif isinstance(othernames, str):
            if "\n" in othernames:
                self._othernames=othernames.split("\n")
            else:
                self._othernames=othernames.split((","))
        self._othernames=[x.strip() for x in self._othernames]



    def __hash__(self):
        return hash(self._name)+sum([hash(x) for x in self._othernames])

    def __eq__(self, other) -> bool:
        return self._name == other._name and all([x == y for x, y in zip(self._othernames, other._othernames)])

    def __str__(self):
        return self._name+", "+self.OtherNamesAsStr(", ")

    def DeepCopy(self) -> "FanzineNames":
        fn=FanzineNames()
        fn._name=self._name
        fn._othernames=[x for x in self._othernames]
        return fn


    @property
    def FullNameAsHTML(self) -> str:
        return "<br>"

    @property
    def MainName(self) -> str:
        return self._name
    @MainName.setter
    def MainName(self, val: str):
        self._name = val

    @property
    def OtherNames(self) -> list[str]:
        return self._othernames
    @OtherNames.setter
    def OtherNames(self, val: list[str]) -> None:
        self._othernames=[x.strip() for x in val]

    @property
    def OtherNamesAsHTML(self) -> str:
        return self.OtherNamesAsStr("<br>")
    @OtherNamesAsHTML.setter
    def OtherNamesAsHTML(self, val: str) -> None:
        fanzinename=SplitOnSpansOfLineBreaks(val)
        if len(fanzinename) > 1:
            self._othernames=fanzinename[1:]
        else:
            self._othernames=[]
        self._othernames=[x.strip() for x in self._othernames]


    def OtherNamesAsStr(self, delim: str) -> str:
        return delim.join(self._othernames)


    def IntepretNewHeader(self, header: str) -> bool:
        # '<a href="https://fancyclopedia.org/ALW_Gazet">ALW Gazet</a> , Antwerpse Letterkundige and Wetenschappelijke Gazet'
        m=re.match(r"<a href=[\'\"]https?://fancyclopedia.org/(.*?)[\'\"]>(.*?)</a>(.*)$", header)
        if m is None:
            return False
        self._name=m.group(2)
        othernames=m.group(3)
        # Othernames can have commas and spaces around it, so strip them
        othernames=othernames.strip().strip(",").strip()
        self._othernames=[othernames]   # TODO: Need to handle multiples
        return True


    def IntepretOldHeader(self, header: str) -> bool:
        # '<a href="https://fancyclopedia.org/ALW_Gazet">ALW Gazet</a> , Antwerpse Letterkundige and Wetenschappelijke Gazet'
        m=re.match(r"<td[^>]*><h1[^>]*>(.*)$", header, flags=re.IGNORECASE)
        if m is None:
            Log(f"IntepretOldHeader('{header}') failed")
            return False
        names=m.group(1)
        names=SplitOnSpansOfLineBreaks(names)
        self._name=names[0]
        self._othernames=names[1:]
        return True


    def SwapMainNameAndOtherName(self, index: int) -> None:
        mainname=self._name
        othername=self._othernames[index]
        self._name=othername
        self._othernames[index]=mainname
