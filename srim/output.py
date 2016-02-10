""" Read output files of SRIM simulation

TODO: Read header information
"""
import os
import re
from io import BytesIO

import numpy as np

double_regex = r'[-+]?\d+\.\d+(?:[eE][-+]?\d+)?'
int_regex = '[+-]?\d+'

class SRIM_Output(object):
    def read_name(self, output):
        raise NotImplementedError()

    def read_target_materail(self):
        raise NotImplementedError()

    def read_table(self, output):
        match = re.search((
            b'=+(.*)'
            b'-+(?:\s+-+)+'
        ), output, re.DOTALL)
        # Read Data from table
        
        if match:
            # Headers TODO: name the columns in table
            header = None

            # Data
            data = np.genfromtxt(BytesIO(output[match.end():]), max_rows=100)
            return data
        return None


class Ioniz(SRIM_Output):
    def __init__(self, directory, filename='IONIZ.txt'):
        with open(os.path.join(directory, filename), 'rb') as f:
            output = f.read()
            data = self.read_table(output)

            if data is None:
                raise Exception('{} in bad IONIZ format'.format(filename))

        self._depth = data[:, 0]
        self._ions = data[:, 1]
        self._recoils = data[:, 2]

    @property
    def depth(self):
        """ Depth [Ang] of bins in SRIM Calculation """
        return self._depth

    @property
    def ions(self):
        """Ionization energy [eV/(Angstrom Ion)] lost to electronic stopping
        in incident ions

        """
        return self._ions

    @property
    def recoils(self):
        """Ionization energy [eV/(Angstrom Ion)] lost to electronic stopping
        in recoil ions
        """
        return self._recoils


class Vacancy(SRIM_Output):
    """ Table of the final distribution of vacancies """
    def __init__(self, directory, filename='VACANCY.txt'):
        with open(os.path.join(directory, filename), 'rb') as f:
            output = f.read()
            data = self.read_table(output)

            if data is None:
                raise Exception('{} in bad VACANCY format'.format(filename))

        self._depth = data[:, 0]
        self._ion_knock_ons = data[:, 1]
        self._vacancies = data[:, 2:]

    @property
    def depth(self):
        """ Depth [Ang] of bins in SRIM Calculation """
        return self._depth

    @property
    def knock_ons(self):
        """ Vacancies produced [Vacancies/(Angstrom-Ion) by ion] """
        return self._ion_knock_ons

    @property
    def vacancies(self):
        """ Vacancies produced of element in layer 

        TODO: improve interface
        """
        return self._vacancies


class NoVacancy(SRIM_Output):
    """ Table of Replacement Collisions """
    def __init__(self, directory, filename='NOVAC.txt'):
        with open(os.path.join(directory, filename), 'rb') as f:
            output = f.read()
            data = self.read_table(output)

            if data is None:
                raise Exception('{} in bad NOVAC format'.format(filename))

        self._depth = data[:, 0]
        self._number = data[:, 1]

    @property
    def depth(self):
        """ Depth [Ang] of bins in SRIM Calculation """
        return self._depth

    @property
    def number(self):
        """ Replacement Collisions [Number/(Angstrom-Ion)]"""
        return self._number


class EnergyToRecoils(SRIM_Output):
    """ Energy transfered to atoms through binary collision """
    def __init__(self, directory, filename='E2RECOIL.txt'):
        with open(os.path.join(directory, filename), 'rb') as f:
            output = f.read()
            data = self.read_table(output)

            if data is None:
                raise Exception('{} in bad E2RECOIL format'.format(filename))

        self._depth = data[:, 0]
        self._ions = data[:, 1]
        self._recoils = data[:, 2:]

    @property
    def depth(self):
        """ Depth [Ang] of bins in SRIM Calculation """
        return self._depth

    @property
    def ions(self):
        """ Energy [eV/(Angstrom-Ion)] transfered to material through ion collisions """
        return self._ions

    @property
    def absorbed(self):
        """ Energy [eV/(Angstrom-Ion)] absorbed from collisions with Atom 

        TODO: fix terminology
        """
        return self._recoils


class Range(object):
    """ Table of the final distribution of the ions, and any recoiling target atoms
    """
    pass


class Backscat(object):
    """ The kinetics of all backscattered ions (energy, location and trajectory)
    """
    pass


class Transmit(object):
    """ The kinetics of all transmitted ions (energy, location and trajectory)
    """
    pass


class Sputter(object):
    """ The kinetics of all target atoms sputtered from the target.
    """
    pass


class Collision:
    """Reads the SRIM Collisions.txt file

    """
    def __init__(self, filename):
        self.filename = filename

        with open(filename, "r", encoding="latin-1") as f:
            self._read_header(f)

        self._ion_index = buffered_findall(filename, b"  Ion    Energy")

    def _read_header(self, f):
        """Read Header of COLLISIONS.TXT

        Currently we do nothing with the header

        """

        # Collect the header of the file
        header = []

        for line in f:
            if line == " \n":
                break
            header.append(line)
        return header

    def _read_ion(self, ion_str):
        """There are 2 types of files with and without cascades

        format:
           1 - Kinchin-Pease Theory (No full cascades)
           2 - full cascades
        """
        # Notice that lines is an generator!
        # This makes it so we can walk through lines
        # in multiple for loops
        lines = (line for line in ion_str.split('\n'))

        # Skip Ion Header
        for line in lines:
            if re.match("^-+\r$", line):
                break

        collisions = []

        # Reads collisions for an ion
        for line in lines:
            if re.match("^=+\r$", line):
                break

            tokens = line.split(chr(179))[1:-1]

            # Check if a full_cascades simulation
            # Read Cascade information
            if re.match(r"\s+<== Start of New Cascade\s+", tokens[-1]):
                (target_disp,
                 target_vac,
                 target_replac,
                 target_inter,
                 cascade) = self._read_cascade(lines)
            else:
                target_disp = float(tokens[8])
                target_vac = 0
                target_replac = 0
                target_inter = 0
                cascade = None

            collisions.append({
                'ion_number': int(tokens[0]),
                'kinetic_energy': float(tokens[1]),
                'depth': float(tokens[2]),
                'lat_y_dist': float(tokens[3]),
                'lat_z_dist': float(tokens[4]),
                'stopping_energy': float(tokens[5]),
                'atom': re.search("([A-Z][a-z])", tokens[6]).group(1),
                'recoil_energy': float(tokens[7]),
                'target_disp': target_disp,
                'target_vac': target_vac,
                'target_replac': target_replac,
                'target_inter': target_inter,
                'cascade': cascade
            })

        # Reads ion footer
        ion_number = re.search(int_regex, next(lines)).group(0)

        footer = ""
        for line in lines:
            if re.match("^=+\r$", line):
                break
            footer += line

        matches = re.findall(double_regex, footer)

        line = next(lines)

        return {
            'ion_number': int(ion_number),
            'displacements': float(matches[0]),
            'avg_displacements': float(matches[1]),
            'replacements': float(matches[2]),
            'avg_replacements': float(matches[3]),
            'vacancies': float(matches[4]),
            'avg_vacancies': float(matches[5]),
            'interstitials': float(matches[6]),
            'avg_interstitials': float(matches[7]),
            'sputtered_atoms': float(matches[8]),
            'avg_sputtered_atoms': float(matches[9]),
            'transmitted_atoms': float(matches[10]),
            'avg_transmitted_atoms': float(matches[11]),
            'collisions': collisions
        }

    def _read_cascade(self, lines):
        line = next(lines)

        assert re.match("^=+\r$", line)

        line = next(lines)
        assert re.match((
                "  Recoil Atom Energy\(eV\)   X \(A\)      Y \(A\)      Z \(A\)"
                "   Vac Repl Ion Numb \d+="
        ), line)

        cascade = []
        for line in lines:
            if re.match("^=+\r$", line):
                break
            tokens = line.split()[1:-1]

            cascade.append({
                'recoil': int(tokens[0]),
                'atom': int(tokens[1]),
                'recoil_energy': float(tokens[2]),
                'position': np.array([float(tokens[3]),
                                      float(tokens[4]),
                                      float(tokens[5])]),
                'vac': int(tokens[6]),
                'repl': int(tokens[7])
            })

        line = next(lines)
        tokens = line.split(chr(179))[1:-1]

        target_disp = float(tokens[2])
        target_vac = float(tokens[3])
        target_replac = float(tokens[4])
        target_inter = float(tokens[5])

        return target_disp, target_vac, target_replac, target_inter, cascade

    def __getitem__(self, i):
        start = self._ion_index[i]

        if i == len(self._ion_index):
            end = os.path.getsize(self.filename)
        else:
            end = self._ion_index[i+1]

        with open(self.filename, "rb") as f:
            f.seek(start)
            # We assume that ion_str will fit in RAM
            ion_str = f.read(end - start)
            return self._read_ion(ion_str.decode('latin-1'))

    def __len__(self):
        return len(self._ion_index) - 1


def buffered_findall(filename, string, start=0):
    with open(filename, 'rb') as f:
        filesize = os.path.getsize(filename)
        BUFFERSIZE = 4096
        overlap = len(string) - 1
        buffer = None
        positions = []

        if start > 0:
            f.seek(start)

        while True:
            if (f.tell() >= overlap and f.tell() < filesize):
                f.seek(f.tell() - overlap)
            buffer = f.read(BUFFERSIZE)
            if buffer:
                buffer_positions = [m.start() for m in re.finditer(string, buffer)]

                for position in buffer_positions:
                    if position >= 0:
                        positions.append(f.tell() - len(buffer) + position)
            else:
                return positions
