import os.path
from dataclasses import dataclass, field
from Log import LogError, Log
import re

from HelpersPackage import CanonicizeColumnHeaders, Bailout, StripSpecificTag, FindAnyBracketedText, RemoveHyperlink
from HelpersPackage import FindIndexOfStringInList, FanzineNameToDirName, ContainsBracketedText, Match2AndRemove


@dataclass(order=False)
class LSTFile:
    FanzineName: str=""
    Editors: str=""
    Dates: str=""
    FanzineType: str=""

    TopComments: list[str] = field(default_factory=list)
    Locale: list[str] = field(default_factory=list)
    ColumnHeaders: list[str] = field(default_factory=list)        # The actual text of the column headers
    Rows: list[list[str]] = field(default_factory=list)

    Complete: bool=False
    AlphabetizeIndividually: bool=False


    #---------------------------------
    # Read an LST file, returning its contents as an LSTFile
    def Load(self, filename: str) -> None:

        # Open the file, read the lines in it and strip leading and trailing whitespace (including '\n')
        try:
            open(filename, "r")
        except Exception as e:
            Bailout(e, "Couldn't open "+filename+" for reading", "LST.read")

        # This is really ugly!  One LST file (that I know of) has the character 0x92 (a curly quote) which is somehow bogus (unclear how)
        # I prefer to use just plain-old-Python for reading the LST file, but it triggers an exception on the 0x92
        # In that case, I read the file using cp1252, a Windows character set which is OK with 0x92.
        try:
            contents=list(open(filename))
        except:
            f=open(filename, mode="rb")
            contents=f.read()
            f.close()
            contents=contents.decode("cp1252").split("\r\n")
        contents=[l.strip() for l in contents]

        if len(contents) == 0:
            return

        # Collapse all runs of empty lines down to a single empty line
        output=[]
        for c in contents:
            if not c:   # If the current line is empty
                if output and output[-1]:   # Was the last line empty too?
                    continue        # Yes: Skip the current line
            output.append(c)
        contents=output
        if not contents:
            return

        # The structure of an LST file is
        #   Header line
        #   (blank line)
        #   Repeated 0 or more times:
        #       <P>line...</P> blah, blah, blah
        #           (This may extend over many lines)
        #       (blank line)
        #   Index table headers
        #   (blank line)
        #   Repeated 0 or more times:
        #       Index table line
        # The table contains *only* tablelines (see below) and empty lines
        # Then maybe some more random bottom text lines


        # The header is ill-defined stuff
        # ALL table lines consist of one instance of either of the characters ">" or ";" and two more of ";", all separated by spans of other stuff.
        # No lines of that sort appear in the toplines section

        # Rummage through the whole file looking for fanac keywords
        # They are comments of the form: <!-- Fanac-keywords: Alphabetize individually-->
        for line in contents:
            if m:=re.search("<!-- Fanac-keywords: (.*)-->", line.strip()):
                # Now search a list of recognized keywords
                if "alphabetize individually" in m.groups()[0].lower():
                    self.AlphabetizeIndividually=True
                    break   # Since this is the one (and only) for now

        # The first non-empty line is the first line. (Since we've already collapsed runs of multiple empty lines to one, we only have to check the 1st line.)
        if not contents[0]:
            contents.pop(0)
        firstLine=contents.pop(0)
        # The Firstline is Name;Editor;Dates;Type, so parse it into fields
        parsed=firstLine.split(";")
        if len(parsed) > 0:
            self.FanzineName=parsed[0]
        if len(parsed) > 1:
            self.Editors=parsed[1]
        if len(parsed) > 2:
            self.Dates=parsed[2]
        if len(parsed) > 3:
            self.FanzineType=parsed[3].strip()

        # Inline function to test if a line is a table cols
        # Because we have already extracted the top line (which looks line a table line), we can use this function to detect the column headers
        def IsTableLine(s: str) -> bool:
            # Column header pattern is at least three repetitions of <a span of at least one character followed by a semicolon or '>'>
            # And there's also the messiness of the first column having an A>B structure
            return re.search(".+[>;].+;.+;", s) is not None

        # Go through the lines one-by-one, looking for a table line. Until that is found, accumulate toptext lines
        # Be on the lookout for Locale lines (bracketed by <<fanac-type>>)
        # Once we hit the table, we move to a new loop.
        self.TopComments=[]
        self.Locale=[]
        rowLines=[]     # This will accumulate the column header line and cols lines
        colHeaderLine=""
        inFanacType=False
        while contents:
            line=contents.pop(0).strip()    # Pop the first line from the list of lines
            if len(line) == 0:
                continue    # Skip blank lines
            m=re.search("<!-- Fanac-keywords: (.*)-->", line.strip())
            if m is not None:
                continue    # We ignore all Fanac-keywords lines as they are meant to be invisible and are handled elsewhere
            if IsTableLine(line):   # If we come to a table line, we have found the column headers (which must start the table). Save it and then drop down to table cols processing.
                colHeaderLine=line
                break
            # Once we find a line that starts with <fanac-type>, we append the lines to locale until we find a line that ends with </fanac-type>
            # We remove leading and trailing <fanac-type> and <h2>
            if inFanacType or line.lower().startswith("<fanac-type>"):
                while line.lower().startswith("<fanac-type>"):  # Must deal with duplicated HTML tags in some broken pages
                    line=StripSpecificTag(StripSpecificTag(line, "fanac-type"), "h2")   # Strip off the tags until there are none left
                self.Locale.append(line)
                if not line.lower().endswith("</fanac-type>"):
                    inFanacType=True
                    continue
                inFanacType=False
            else:
                self.TopComments.append(line.strip().removeprefix("<p>").removesuffix("</p>"))

        # Time to read the table header and rows
        while contents:
            line=contents.pop(0).strip()    # Grab the top line
            if not line:
                continue    # Skip blank lines
            if not IsTableLine(line):
                break       # If we hit a line that is not a table line, we must be past the table
            rowLines.append(line)

        # Change the column headers to their standard form
        self.ColumnHeaders=[CanonicizeColumnHeaders(h.strip()) for h in colHeaderLine.split(";") if len(h) > 0]

        # And likewise the rows
        # We need to do some special processing on the first two columns.  In the LST file they are combined into a single column,
        # and here we expand this to two for processing.  In all cases, the input is the 1st ;-separated group in a line of the LST file
        self.Rows=[]
        for row in rowLines:
            cols=[x.strip() for x in row.split(";")]
            lstrow=self.LSTToRow(cols[0])+cols[1:]
            self.Rows.append(lstrow)

        # Define the grid's columns
        # First add the invisible column which is actually the link destination
        # It's the first part of the funny xxxxx>yyyyy thing in the LST file's 1st column
        self.ColumnHeaders=["Filename"]+self.ColumnHeaders

        # If any rows are shorter than the headers cols, pad them with blanks
        for row in self.Rows:
            if len(row) < len(self.ColumnHeaders):
                row.extend([""]*(len(self.ColumnHeaders)-len(row)))

        # The Mailings column probably contains HTML links to the APA mailings, but we only want to display the markup test (e.g., "FAPA 23A") to the user.
        # Strip away the html -- we'll add it back in on saving.
        # Note that some older LST files have variant headers.
        iMailings=FindIndexOfStringInList(self.ColumnHeaders, ["mailing", "mailings", "apa mailing", "apa mailings"], IgnoreCase=True)
        if iMailings is not None:
            for row in self.Rows:
                row[iMailings]=RemoveHyperlink(row[iMailings], repeat=True)


    # Remove a leading http[s]//[www.]fanac.org/fanzines, f present.
    @staticmethod
    def RemoveUnneededStartToURL(s: str) ->str:
        pattern="(https?://)"
        prefix=""
        m=re.match(pattern, s)
        if m is not None:
            prefix=m.groups()[0]
            s=re.sub(pattern, "", s, 1, re.IGNORECASE)

        pattern="(www.)?fanac.org/fanzines/"
        m=re.match(pattern, s)
        if m is not None:
            s=re.sub(pattern, "", s, 1, re.IGNORECASE)
            return s

        return prefix+s


    @staticmethod
    def LSTToRow(col0: str) -> list[str, str]:
        col0=col0.strip()
        print(f"****\nCol0={col0}")

        # Case 0
        # If the line has no content (other than ">" and ";" and whitespace, append two empty strings
        if re.match("^[>;\s]*$", col0):
            out=([""]*2)
            print(f"LSTToRow Case 0: {out}")
            return out

        # Case 1: We have a full-fledged href, perhaps followed by some random text
        pattern="^<a href=\"https?:\/\/([^>]*)\">(.*)$"     # <a href=url>text
        _, url, text=Match2AndRemove(col0, pattern)
        if url and text:
            if "fanac.org/fanzines/" in url:
                url=url.removeprefix("fanac.org/fanzines/")
                out=[url, text]
                print(f"LSTToRow Case 1: {out}")
                return out

        # Case 2:   {filename}>{text w/o HTML}
        # We have a ">", but no brackdted text.
        # This is by far the most common case
        if not ContainsBracketedText(col0):
            # Look for case (2), and add the ">" to make it case (1)
            out=LSTFile.SplitOnPointyBracket(col0)
            if out != ["", ""]:
                print(f"LSTToRow Case 2: {out}")
                return out

        # Case 3:  {<a name=..>}>{text}   (an anchor)
        # This one is easy
        m=re.match("(<a\s+name=.*?>)(?:</a>|>)?(.*?)$", col0, re.IGNORECASE)  # Note that the 2d group is non-capturing
        if m is not None:
            out=[m.groups()[0], m.groups()[1]]
            print(f"LSTToRow Case 3: {out}")
            return out

        # Case 4: Does col 0 contain a full hyperlink?
        m=re.match("<a\s+href=\"?(https?)://(.*?/?)\"?>(.*?)(</a>)?$", col0, re.IGNORECASE)
        if m is not None:
            url=m.groups()[1]
            disptext=m.groups()[2]
            # We're looking at a full URL w/o surrounding HTML
            out=[f"{m.groups()[0]}://{url}"]+[disptext]
            print(f"LSTToRow Case 4: {out}")
            return out

        # Case 5: At this point, if there is bracketed text left, we're seeing some sort of HTML decoration and not a fanzine cols
        if col0.startswith("<"):
            _, bracket, contents, rest=FindAnyBracketedText(col0)
            if len(bracket+contents+rest) > 0:
                out=[f"<{bracket}>{contents}</{bracket}>", rest]
                print(f"LSTToRow Case 5: {out}")
                return out

        Log(f"###############################################\n***** LST2Row is failing!: {col0}")
        return ["", ""]



    @staticmethod
    def SplitOnPointyBracket(col0: str) -> list[str, str]:
        if ">" not in col0:
            col0=">"+col0.strip()  # Because there are some cases where there is no filename. The ">" is missing so we need to supply one.
        # Apparently there may still be cases where the ">" was a ">>".  Fix this.
        col0=col0.replace(">>", ">")
        if col0.count(">") != 1:
            Log(f"SplitOnPointyBracket() failure: Too many '>' in {col0}")
            return ["", ""]
        # Now we can handle them all as case (1)
        out=col0.split(">")
        return out


    # Does the string contain HTML not associated with a hyperlink?
    # E.g., <b>, <a name=>, etc
    @staticmethod
    def IsDecorated(s: str) -> bool:
        s=s.lower()
        if "http:" in s or "https:" in s or "href=" in s:
            return False

        if "<b>" in s or "<p>" in s or "<a name=" in s or "<i>" in s:
            return True

        return False


    # ---------------------------------
    # Format the data and save it as an LST file on disk
    def Save(self, pathname: str) -> bool:

        Log(f"Save({pathname})")
        content=[f"{self.FanzineName};{self.Editors};{self.Dates};{self.FanzineType}", ""]

        if self.TopComments and "".join(self.TopComments):    # Only write these lines if there is at least one non-empty line
            for line in self.TopComments:
                content.append(f"<p>{line}</p>")
            content.append("")

        if self.Locale:
            for line in self.Locale:
                content.append(f"<fanac-type><h2>{line}</h2></fanac-type>")
            content.append("")

        if self.AlphabetizeIndividually:
            content.append("<!-- Fanac-keywords: Alphabetize individually -->\n")

        # Go through the headers and rows and trim any trailing columns which are entirely empty.
        # First find the last non-empty column
        if not self.Rows:
            return False
        maxlen=max([len(row) for row in self.Rows])
        maxlen=max(maxlen, len(self.ColumnHeaders))
        lastNonEmptyColumn=maxlen-1     # lastNonEmptyColumn is an index, not a length
        while lastNonEmptyColumn > 0:
            if len(self.ColumnHeaders[lastNonEmptyColumn]) > 0:
                break
            found=False
            for row in self. Rows:
                if len(row[lastNonEmptyColumn]) > 0:
                    found=True
                    break
            if found:
                break
            lastNonEmptyColumn-=1

        # Do we need to trim?
        if lastNonEmptyColumn < maxlen-1:    # lastNonEmptyColumn is an index, not a length
            self.ColumnHeaders=self.ColumnHeaders[:lastNonEmptyColumn+1]
            self.Rows=[row[:lastNonEmptyColumn+1] for row in self.Rows]

        # Write out the column headers
        # Need to remove the "Filename" column which was added when the LST file was loaded.  It is the 1st col.
        content.append("; ".join(self.ColumnHeaders[1:]))

        # Turn any mailing info into hyperlinks to the mailing on fanac.org
        iMailings=FindIndexOfStringInList(self.ColumnHeaders, ["mailing", "mailings", "apa mailing", "apa mailings"], IgnoreCase=True)
        if iMailings is not None:
            self.ColumnHeaders[iMailings]="Mailing"     # Change header to standard in case it isn't
            for row in self.Rows:
                mailing=row[iMailings]
                row[iMailings]=""
                if len(mailing) > 0:
                    mailings=mailing.replace(",", "&").split("&")     # It may be of the form 'FAPA 103 PM, OMPA 32 & SAPS 76A'
                    first=True
                    for mailing in mailings:
                        mailing=mailing.strip()
                        if len(mailing) > 0:
                            if not first:
                                row[iMailings]+=", "    # Add a comma before subsequent mailings
                            first=False
                            m=re.match("([a-zA-Z'1-9_\- ]*)\s+([0-9]+[a-zA-Z]*)\s*(pm|postmailing)?$", mailing, flags=re.IGNORECASE)      # Split the FAPA 103A into an apa name and the mailing number (which may have trailing characters '30A')
                            if m is not None:
                                apa=m.groups()[0]
                                number=m.groups()[1]
                                pm=m.groups()[2]
                                if pm:
                                    pm=" "+pm
                                else:
                                    pm=""
                                row[iMailings]+=f'<a href="https://fanac.org/fanzines/APA_Mailings/{FanzineNameToDirName(apa)}/{number}.html">{apa} {number}</a>{pm}'


        # Do not save trailing empty rows
        if len(self.Rows) > 1:
            lastNonEmptyRow=len(self.Rows)-1
            while lastNonEmptyRow > 0:
                if any([x.strip() != "" for x in self.Rows[lastNonEmptyRow]]):
                    break
            if lastNonEmptyRow < len(self.Rows)-1:
                self.Rows=self.Rows[:lastNonEmptyRow+1]

        # Now lst file can have fewer than three columns.
        if len(self.Rows[0]) < 3:  # Smallest possible LST file
            LogError(f"LSTfile.Save(): {pathname} has {len(self.Rows)} columns which is too few. Not saved")
            return False

        # Now save the spreadsheet rows.  Note that the list of rows is trimmed so that each has the same length
        # Convert each cols in the GUI interface to a cols in the LST file
        for row in self.Rows:
            row=[x.strip() for x in row]    # Remove any leading or trailing blanks

            # The first two columns require special handing.
            cols01=self.RowToLST(row[0:2])
            # if cols01 == "":
            #     cols01=f"{row[0]}>{row[1]}"
            content.append(f"{cols01}; {'; '.join(row[2:])}")

        # And write it out
        with open(pathname, "w+") as f:
            Log(f"Writing {pathname}")
            f.writelines([c+"\n" for c in content])

        return True


    # Take the first two columns of the spreadsheet and generate the LST file string for them
    @staticmethod
    def RowToLST(cols: list[str, str]) -> str:

        cols[0]=cols[0].strip()       # Just to be sure
        print(f"****\n{cols=}")

        # Case 1: nothing in col 0 and hence there is no possibility of a link of any sort.
        if len(cols[0].strip()) == 0:
            out=f"{cols[1]}"
            print(f"Row2LST Case 1: {out}")
            return out

        # Case 2:   {filename}>{text w/o HTML}
        # This is the most common (by far!) case
        # There are no slashes or tags in col 0 (the filename); The text (col 1) does not contain HTML
        if "/" not in cols[0] and '\\' not in cols[0]:
            if not ContainsBracketedText(cols[1]):
                out=f'{cols[0]}>{cols[1]}'
                print(f"Row2LST Case 2: {out}")
                return out

        # Case 3: If col 0 starts 'http[s]:' we take it as a bare URL and clothe it in HTML
        if cols[0].lower().startswith("http:") or cols[0].lower().startswith("https:"):
            out=f'<a href="{cols[0]}">{cols[1]}'
            print(f"Row2LST Case 3: {out}")
            return out

        # Case 4: We have a partial path/filename
        pathname, ext=os.path.splitext(cols[0])
        if not ContainsBracketedText(pathname) and len(ext) > 0:
            # Jack's code requires that this be an href
            out=f'<a href="https://fanac.org/fanzines/{cols[0]}">{cols[1]}'
            print(f"Row2LST Case 4: {out}")
            return out

        # Case 5: The filename (col 0) does not contain HTML and does end with a slash (thus having no extension), which indicates that it is a directory
        # We make this into a href to placate Jack's code
        if not LSTFile.IsDecorated(cols[0]) and cols[0][-1] == "/":
            out=f'<a href="https://fanac.org/fanzines/{cols[0]}">{cols[1]}'
            print(f"Row2LST Case 5: {out}")
            return out

        # Case 6:  {<a name=..>}>{text}   (an anchor)
        m=re.match("(<a\s+name=[^<>]+>)", cols[0])
        if m is not None:
            out=cols[0]+cols[1]     # Note no ">".  Jack's weirdness
            print(f"Row2LST Case 6: {out}")
            return out

        # TODO: Isn't this really the case where col 0 has text that isn't a hyperlink and col 1 is empty?  Should this also include Case 3???
        # Case 7 is the case where there is no link in col 0, but there is text that is used for things like separation of different kinds of fanzines.
        #   This text may be decorated with html (e.g., <b>xx</b>) and the html must be preserved.
        #   Col 0 will be something like <b>xx</b> and Col 1 will be blank
        if re.search(r"<([b-zB-Z].*)>.*</\1>", cols[0].lower().strip()):  # If there is a <xxx>...</xxx> in the 1st col and xxx does not start with A, we have a non-link
            assert len(cols[1].strip()) == 0
            out=f"{cols[0]};"
            print(f"Row2LST Case 7: {out}")
            return out

        #TODO: Is this case needed?
        # Case 8: A href back into fanac.org
        if cols[0].startswith("../"):
            col1=f"<a href=\"https://fanac.org/fanzines/{cols[0].removeprefix('../')}\">{cols[1]}"
            out=f"{col1};"
            print(f"Row2LST Case 8: {out}")
            return out

        #TODO: Is this case needed?
        # Case 9:
        if cols[0].startswith("<a "):
            try:
                m=re.match("<a href=(.*)>(.*)$", cols[0].strip())
                if m is not None:
                    out=f"{cols[0]}{cols[1]}"f"<a href=\"https://{cols[0]}\">{cols[1]}"
                    print(f"Row2LST Case 9: {cols[0]}")
                    return cols[0]

            except:
                pass

        Log(f"###############################################\n***** RowToLST has failed {cols[0]}")
        return ""