from stataLogObject.Configs.ConfigObj import MFVar, Table
from stataLogObject.Supports.supports import extract_values, clean_value
from stataLogObject.Supports.Errors import HeaderKeyExtractError, InvalidKeyExtract


class StataTable:
    def __init__(self, raw_table, config):
        """
        A generic Stata Table

        :param raw_table: The raw table from StataRaw object
        :type raw_table: list[list]

        :param config: The attributes of the Table to configure with
        :type config: Table

        """

        # Raw table reference and the configuration for this table
        self._raw = raw_table
        self.config = config

        # For the body isolate, create reference and format the indexes relative to the length of the table
        self.iso = self.config.body_iso
        self.iso.format_indexes(len(self._raw))

        # Set the supporting table header values
        [setattr(self, f, self.set_mf_value(getattr(self.config.mf, f), f)) for f in self.config.mf.field_names()]
        self.model_fit = {f: getattr(self, f) for f in self.config.mf.field_names() if getattr(self, f) is not None}

        # Extract phenotype, variable names, and the table body
        self.phenotype, self.body_values = self._extract_body()

    def set_mf_value(self, mf_var, var_name):
        """
        Set a given model fit value

        :param mf_var: The model fit variables attributes to use to isolate this model fit variable
        :type mf_var: MFVar | None

        :param var_name: The name of this header for Error Handling
        :type var_name: str

        :return: The numeric values of the header supporting values
        :rtype: float | int

        :raises HeaderKeyExtractError InvalidKeyExtract: If the header.key_extract leads to a KeyError and No line found
            for header.extractor respectively
        """

        # Some Headers are optional, return None if this occurs
        if not mf_var:
            return None

        for line in self._raw:

            line_str = " ".join(line)
            if mf_var.extractor in line_str:
                values = extract_values(line_str)

                # Some variables may be found, but not set. For example F stat when very small sample. Warn user when
                # this happens as it could also be due to an issue of extraction
                if len(values) == 0:
                    print(f"Warning: {var_name} not set yet requested")
                    return "N/A"

                # Try to return the value with the given header.key_extract index (default 0)
                else:
                    try:
                        return mf_var.var_type(values[mf_var.key_extract])
                    except (KeyError, IndexError):
                        raise HeaderKeyExtractError(mf_var.key_extract, values, var_name)

        raise InvalidKeyExtract(mf_var.extractor, var_name)

    def _extract_body(self):
        """
        This extracts the body of the table by looking for the stata dividers and then parsing out the unique elements.
        Use the first element of the first line as the phenotype, and then return the rest as column headers will be set
        based on table type.

        :return: A str of the phenotype and a list of TableEntry
        :rtype: (str, list[TableEntry])
        """

        # Isolate results with tables based on table line delimiters, skip indexes in the skip_indexes if provided
        result_indexes = [i for i, line in enumerate(self._raw) if ("|" in line) and (i not in self.iso.skip_indexes)]

        # Isolate these lines without the table line elements
        body_lines = self._extract_body_lines(result_indexes)

        # # Extract the variable names, with the first one always being the phenotype/outcome
        phenotype = body_lines[0][0]

        # Return the phenotype, variable names, and the table bodies formatted values
        return phenotype, self._create_table_entries(body_lines)

    def _extract_body_lines(self, result_indexes):
        """
        This will strip out the lines without the table line elements.

        :param result_indexes: The indexes of the results table
        :type result_indexes: list[int]

        :return: A list of each row that is in the table body
        :rtype: list[list[str]]
        """
        body_lines = []
        for index, line in enumerate(self._raw):
            # TODO: This feels like a very strange if statement...
            if min(result_indexes) + self.iso.skip_lines <= index and index in result_indexes:

                # Not all regression types will be without blanks, so this only adds rows that where the value is more
                # than just he name of the variable
                values_stripped = [value for value in line if value != "|"]
                if len(values_stripped) > 1:
                    body_lines.append(values_stripped)
        return body_lines

    def _create_table_entries(self, body_lines):
        """Clean the values which are not the table header, create Entry of type Body_Type for each line accordingly"""
        return [self.iso.body_type.create_entry(line) for line in self._limit_var_names(body_lines)]

    def _limit_var_names(self, body_lines):
        """
        Extract the values then format them

        Note
        ----
        After extracting the values, it is possible that space seperated names may lead to more elements in a row than
        there are columns to accept them. Here after extracting the values, we format them relative to the length of
        table headers

        :param body_lines: Each line from the body that is a variable result
        :type body_lines: list[list[str]]

        :return: Formatted lines
        :rtype: list[list]
        """
        value_lines = [[clean_value(value) for value in line] for line in body_lines[1:]]
        return [line if len(line) == len(self.config.headers) else self._line_format(line) for line in value_lines]

    def _line_format(self, line):
        """Format line relative to the number of table headers"""
        values = line[-(len(self.config.headers) - 1):]
        var_name = "_".join(line[:-(len(self.config.headers) - 1)])
        return [var_name] + values

    @property
    def var_names(self):
        """Variable names"""
        return [b.var_name for b in self.body_values]

    @property
    def coefficients(self):
        """The coefficients"""
        return [b.coefficient for b in self.body_values]

    @property
    def std_errors(self):
        """The standard error"""
        return [b.std_err for b in self.body_values]

    @property
    def probability(self):
        """The two tailed probability relative to P values or Z scores"""
        return [b.prob for b in self.body_values]

    @property
    def lb_95(self):
        """95% Confidence internal lower bound"""
        return [b.lb_95 for b in self.body_values]

    @property
    def ub_95(self):
        """95% Confidence internal upper bound"""
        return [b.ub_95 for b in self.body_values]

    @property
    def p_z_value(self):
        """The p stat or z score depending on the table"""
        if self.config.body_iso.p_value:
            return [b.entry_values()['p_value'] for b in self.body_values]
        else:
            return [b.entry_values()['z_score'] for b in self.body_values]
