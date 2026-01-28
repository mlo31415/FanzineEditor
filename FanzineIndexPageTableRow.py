from __future__ import annotations

from WxDataGrid import ColDefinitionsList, GridDataRowClass
from HelpersPackage import CanonicizeColumnHeaders

#=============================================================
# An individual fanzine to be listed in a fanzine index table
# This is a single row
class FanzineIndexPageTableRow(GridDataRowClass):

    def __init__(self, coldefs: ColDefinitionsList, row: None | list[str]=None) -> None:
        GridDataRowClass.__init__(self)
        self.FileSourcePath: str=""
        self._tableColdefs=coldefs
        self._Signature: int=0
        self._UpdatedComment: str=""
        if row is None:
            self._cells=[""]*len(self._tableColdefs)
        else:
            if len(self._tableColdefs) != len(row):
                raise Exception("FanzineIndexPageTableRow.__init__() row length must match column definitions length.")
            self._cells=row

        # Is this a text row, i.e., a row that is just a single line of text?
        # (Note that rows with issue info, but no issue, look a lot like text rows and must be detected by checking for stuff in other cells.)
        if self._cells[0] == "" and len(self._cells[1]) > 0 and not any([x != "" for x in self._cells[2:]]):
            # There is text only in cell 1 and nowhere else
            # In a text row, the text now is stored in cell 0, so swap them
            self._isText: bool=True
            self._cells[0]=self._cells[1]
            self._cells[1]=""
        else:
            self._isText=False

        self._isLink: bool=False        # Is this a link? (I.e., a row that has a link in cell 0/1 and nothing else?)
        self._URL: str=""               # The URL to be used for a link. (This is ignored if _isLink == False.)
                                        # It will be displayed using the localfilename as the link text.
                                        # Note that this is different than the URL method in the other frames


    def __str__(self) -> str:      # FanzineTableRow(GridDataRowClass)
        return str(self._cells)

    def __len__(self) -> int:     # FanzineTableRow(GridDataRowClass)
        return len(self._cells)

    def Extend(self, s: list[str]) -> None:
        self._cells.extend(s)

    # Make a deep copy of a FanzineTableRow
    def Copy(self) -> FanzineIndexPageTableRow:
        val=FanzineIndexPageTableRow(self._tableColdefs)
        val._cells=[x for x in self._cells]     # Make a new list containing the old cell data
        return val

    def Signature(self) -> int:
        return "".join(self._cells).__hash__()

    @property
    def CanDeleteColumns(self) -> bool:
        return True

    # This deletes a single column from the datasource.
    # It must be implemented here because WxDataGrid doesn't understand the details of the DataSource
    def DelCol(self, icol: int) -> None:
        del self._cells[icol]

    @property
    def Cells(self) -> list[str]:
        return self._cells
    @Cells.setter
    def Cells(self, val: list[str]) -> None:
        self._cells=val


    # Get or set a value by name or column number
    #def GetVal(self, name: str|int) -> str|int:
    def __getitem__(self, index: str|int|slice) -> str|list[str]|slice:

        if isinstance(index, int):
            if index < 0 or index >= len(self._cells):
                raise IndexError(f"FanzineIndexPageTableRow.__getitem__({index}) index out of range.")
            return self._cells[index]

        if isinstance(index, slice):
            if index.start < 0 or index.stop >= len(self._cells) or index.start >= index.stop:
                raise IndexError(f"FanzineIndexPageTableRow.__getitem__({index}) invalid slice.")
            return self._cells[index]

        # The only valid possibility left is a str (the name of a column).
        if not isinstance(index, str):
            raise Exception(f"FanzineIndexPageTableRow.__getitem__({index}) index must be a string or int.")

        index=CanonicizeColumnHeaders(index)
        if index not in self._tableColdefs:
            raise IndexError(f"FanzineIndexPageTableRow.__getitem__({index}) column not found.")

        index=self._tableColdefs.index(index)
        return self._cells[index]



    def __setitem__(self, index: str|int|slice, value: str|int) -> None:
        if isinstance(value, int):
            value=str(value)    # All data is stored as strings

        if isinstance(index, int):
            if index < 0 or  index >= len(self._cells):
                raise IndexError(f"FanzineIndexPageTableRow.__setitem__({index}) index out of range.")
            self._cells[index]=value
            return

        if isinstance(index, slice):
            raise Exception(f"FanzineIndexPageTableRow.__setitem__({index}) may not be a slice.")
        if not isinstance(index, str):
            raise Exception(f"FanzineIndexPageTableRow.__setitem__({index}) value must be a string or int.")

        index=CanonicizeColumnHeaders(index)
        if index not in self._tableColdefs:
            raise IndexError(f"FanzineIndexPageTableRow.__setitem__({index}) column not found.")

        index=self._tableColdefs.index(index)
        self._cells[index]=value
        return

    @property
    def IsLinkRow(self) -> bool:
        return self._isLink
    @IsLinkRow.setter
    def IsLinkRow(self, val: bool) -> None:
        self._isLink=val

    @property
    def IsTextRow(self) -> bool:
        return self._isText
    @IsTextRow.setter
    def IsTextRow(self, val: bool) -> None:
        self._isText=val

    @property
    def IsNormalRow(self) -> bool:
        return not self.IsLinkRow and not self.IsTextRow

    @property
    def IsEmptyRow(self) -> bool:
        return all([cell.strip() == "" for cell in self._cells])