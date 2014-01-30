# -*- coding: utf-8 -*-
"""Tests for unihan.

cihaidata_unihan.testsuite.unihan
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use datapackage.json format.

1. insert dict/struct of { 'unihanFileName': ['colName', 'colName'] }
return cols, records

    Idea: Create a special iter class for it.
    Idea 2: Function, return cols, struct above

What a data set should provide.

1. Download the code.
2. Extract it (if necessary).
3. Extract the code


"""

from __future__ import absolute_import, division, print_function, \
    with_statement, unicode_literals

import os
import sys
import tempfile
import logging
import unittest
import zipfile
import shutil

try:
    import unittest2 as unittest
except ImportError:  # Python 2.7
    import unittest

from contextlib import contextmanager

from scripts import process

from scripts.process import UNIHAN_URL, UNIHAN_DEST, WORK_DIR, UNIHAN_FIELDS, \
    UNIHAN_FILES, default_config, Builder, text_type, StringIO
from scripts.util import merge_dict


log = logging.getLogger(__name__)


def add_to_path(path):
    """Adds an entry to sys.path if it's not already there.  This does
    not append it but moves it to the front so that we can be sure it
    is loaded.
    """
    if not os.path.isdir(path):
        raise RuntimeError('Tried to add nonexisting path')

    def _samefile(x, y):
        if x == y:
            return True
        try:
            return os.path.samefile(x, y)
        except (IOError, OSError, AttributeError):
            # Windows has no samefile
            return False
    sys.path[:] = [x for x in sys.path if not _samefile(path, x)]
    sys.path.insert(0, path)


def setup_path():
    script_path = os.path.join(
        os.path.dirname(__file__), os.pardir, 'scripts'
    )
    add_to_path(script_path)


def get_datapath(filename):

    return os.path.join(
        os.path.dirname(__file__), 'fixtures', filename
    )


@contextmanager
def captureStdErr(command, *args, **kwargs):
    out, sys.stderr = sys.stderr, StringIO()
    command(*args, **kwargs)
    sys.stderr.seek(0)
    yield sys.stderr.read()
    sys.stderr = out


@contextmanager
def captureStdOut(command, *args, **kwargs):
    out, sys.stdout = sys.stderr, StringIO()
    command(*args, **kwargs)
    sys.stdout.seek(0)
    yield sys.stdout.read()
    sys.stdout = out


class TestCase(unittest.TestCase):
    pass


class UnihanHelper(TestCase):

    config = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        'test_config.yml'
    ))

    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.mkdtemp()
        cls.mock_zip_filename = 'zipfile.zip'
        cls.mock_zip_filepath = os.path.join(cls.tempdir, cls.mock_zip_filename)
        zf = zipfile.ZipFile(cls.mock_zip_filepath, 'a')
        zf.writestr("d.txt", "DDDDDDDDDD")
        zf.close()

        cls.zf = zf

        super(UnihanHelper, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tempdir)
        super(UnihanHelper, cls).tearDownClass()


class UnihanScriptsTestCase(UnihanHelper):

    def test_has_unihan_zip(self):
        self.assertFalse(process.has_unihan_zip())

        self.assertTrue(process.has_unihan_zip(self.mock_zip_filepath))

    def test_in_fields(self):
        columns = ['hey', 'kDefinition', 'kWhat']
        result = process.in_fields('kDefinition', columns)

        self.assertTrue(result)

    def test_filter_manifest(self):
        expected = {
            'Unihan_Variants.txt': [
                'kCompatibilityVariant',
                'kSemanticVariant',
                'kSimplifiedVariant',
                'kSpecializedSemanticVariant',
                'kTraditionalVariant',
                'kZVariant',
            ]
        }

        result = process.filter_manifest(['Unihan_Variants.txt'])

        self.assertEqual(set(result), set(expected))

    def test_get_files(self):
        fields = ['kKorean', 'kRSUnicode']

        expected = ['Unihan_Readings.txt', 'Unihan_RadicalStrokeCounts.txt']

        result = process.get_files(fields)

        self.assertEqual(set(result), set(expected))

    def test_save(self):

        src_filepath = self.mock_zip_filepath

        tempdir = tempfile.mkdtemp()

        dest_filepath = os.path.join(tempdir, self.mock_zip_filename)
        process.save(src_filepath, dest_filepath, shutil.copy)

        result = os.path.exists(dest_filepath)

        shutil.rmtree(tempdir)

        self.assertTrue(result)

    def test_download(self):

        src_filepath = self.mock_zip_filepath

        tempdir = self.tempdir
        dest_filepath = os.path.join(tempdir, 'data', self.mock_zip_filename)

        process.download(src_filepath, dest_filepath, shutil.copy)

        result = os.path.dirname(os.path.join(dest_filepath, 'data'))
        self.assertTrue(
            result,
            msg="Creates data directory if doesn't exist."
        )

    def test_extract(self):

        zf = process.extract(self.mock_zip_filepath)

        self.assertEqual(len(zf.infolist()), 1)
        self.assertEqual(zf.infolist()[0].file_size, 10)
        self.assertEqual(zf.infolist()[0].filename, "d.txt")

    def test_convert_unihan_file_format(self):
        pass

    def test_convert_only_output_requested_columns(self):
        fd, filename = tempfile.mkstemp()

        try:
            os.write(fd, """\
U+3400	kCantonese	jau1
U+3400	kDefinition	(same as U+4E18 丘) hillock or mound
U+3400	kMandarin	qiū
U+3401	kCantonese	tim2
U+3401	kDefinition	to lick; to taste, a mat, bamboo bark
U+3401	kHanyuPinyin	10019.020:tiàn
""".encode('utf-8'))

            csv_files = [
                filename
            ]

            columns = [
                'kTotalStrokes',
                'kPhonetic',
                'kCantonese',
                'kDefinition',
            ] + process.default_columns

            items = process.convert(csv_files, columns)

            notInColumns = []
            inColumns = ['kDefinition', 'kCantonese'] + process.default_columns

            # columns not selected in convert must not be in result.
            for v in items[0]:
                if v not in columns:
                    notInColumns.append(v)
                else:
                    inColumns.append(v)
        finally:
            os.remove(filename)

        self.assertEqual([], notInColumns, msg="Convert filters columns not specified.")
        self.assertTrue(set(inColumns).issubset(set(columns)), "Convert returns correct columns specified + ucn and char.")

    def test_convert_simple_data_format(self):
        """convert turns data into simple data format (SDF)."""
        csv_files = [
            get_datapath('Unihan_DictionaryLikeData.txt'),
            get_datapath('Unihan_Readings.txt'),
        ]

        columns = [
            'kTotalStrokes',
            'kPhonetic',
            'kCantonese',
            'kDefinition',
        ] + process.default_columns

        items = process.convert(csv_files, columns)

        header = items[0]
        self.assertEqual(header, columns)

        rows = items[1:]


class UnihanHelperFunctions(UnihanHelper):

    """Utilities to retrieve unihan data in datapackage format."""

    def test_flatten_fields(self):

        single_dataset = {
            'Unihan_Readings.txt': [
                'kCantonese',
                'kDefinition',
                'kHangul',
            ]
        }

        expected = ['kCantonese', 'kDefinition', 'kHangul']
        results = process.get_fields(single_dataset)

        self.assertEqual(expected, results)

        datasets = {
            'Unihan_NumericValues.txt': [
                'kAccountingNumeric',
                'kOtherNumeric',
                'kPrimaryNumeric',
            ],
            'Unihan_OtherMappings.txt': [
                'kBigFive',
                'kCCCII',
                'kCNS1986',
            ]
        }

        expected = [
            'kAccountingNumeric',
            'kOtherNumeric',
            'kPrimaryNumeric',
            'kBigFive',
            'kCCCII',
            'kCNS1986',
        ]

        results = process.get_fields(datasets)

        self.assertSetEqual(set(expected), set(results))

    def test_pick_files(self):
        """Pick a white list of files to build from."""

        files = ['Unihan_Readings.txt', 'Unihan_Variants.txt']

        config = {
            'files': files,
            'source': self.mock_zip_filepath
        }

        b = process.Builder(config)

        result = b.config.files
        expected = files

        self.assertEqual(result, expected, msg='Returns only the files picked.')

    def test_raise_error_unknown_field(self):
        """Throw error if picking unknown field."""

        config = {
            'fields': ['kHello']
        }

        with self.assertRaisesRegexp(KeyError, 'Field ([a-zA-Z].*) not found in file list.'):
            b = process.Builder(config)

    def test_raise_error_unknown_file(self):
        """Throw error if picking unknown file."""

        config = {
            'files': ['Sparta.lol']
        }

        with self.assertRaisesRegexp(KeyError, 'File ([a-zA-Z_\.\'].*) not found in file list.'):
            b = process.Builder(config)

    def test_raise_error_unknown_field_filtered_files(self):
        """Throw error if picking field not in file list, when files specified."""

        files = ['Unihan_Variants.txt']

        config = {
            'files': files,
            'fields': ['kDefinition'],
        }

        with self.assertRaisesRegexp(KeyError, 'Field ([a-zA-Z].*) not found in file list.'):
            b = process.Builder(config)

    def test_set_reduce_files_automatically_when_only_field_specified(self):
        """Picks file automatically if none specified and fields are."""

        fields = process.UNIHAN_MANIFEST['Unihan_Readings.txt'] + process.UNIHAN_MANIFEST['Unihan_Variants.txt']

        config = {
            'fields': fields,
        }

        b = process.Builder(config)

        expected = ['Unihan_Readings.txt', 'Unihan_Variants.txt']
        results = b.config.files

        self.assertSetEqual(set(expected), set(results))

    def test_set_reduce_fields_automatically_when_only_files_specified(self):
        """Picks only necessary files when fields specified."""

        files = ['Unihan_Readings.txt', 'Unihan_Variants.txt']

        config = {
            'files': files
        }

        b = process.Builder(config)

        expected = process.get_fields(process.filter_manifest(files))
        results = b.config.fields

        self.assertSetEqual(set(expected), set(results), msg='Returns only the fields for files picked.')


class ProcessTestCase(TestCase):

    def test_conversion_ucn_to_unicode(self):
        before = 'U+4E00'
        expected = '\u4e00'

        result = process.ucn_to_unicode(before)

        self.assertEqual(result, expected)

        self.assertIsInstance(result, text_type)

        # wide character
        before = 'U+20001'
        expected = '\U00020001'

        result = process.ucn_to_unicode(before)

        self.assertEqual(result, expected)
        self.assertIsInstance(result, text_type)

        before = '(same as U+7A69 穩) firm; stable; secure'
        expected = '(same as 穩 穩) firm; stable; secure'

        result = process.ucnstring_to_unicode(before)

        self.assertEqual(result, expected)
        self.assertIsInstance(result, text_type)


class CliArgTestCase(UnihanHelper):

    """Allows for creating a custom output of unihan data
    in datapackage.json format."""

    def test_no_args(self):
        """Works without arguments."""

        expected = default_config
        result = Builder.from_cli([]).config

        self.assertEqual(expected, result)

    def test_cli_plus_defaults(self):
        """Test CLI args + defaults."""

        expectedIn = {'source': self.mock_zip_filepath}
        result = Builder.from_cli(['-s', self.mock_zip_filepath]).config
        self.assertDictContainsSubset(expectedIn, result)

        expectedIn = {'fields': ['kDefinition']}
        result = Builder.from_cli(['-F', 'kDefinition']).config
        self.assertDictContainsSubset(expectedIn, result)

        expectedIn = {'fields': ['kDefinition']}
        result = Builder.from_cli(['-F', 'kDefinition']).config
        self.assertDictContainsSubset(expectedIn, result)

        expectedIn = {'fields': ['kDefinition', 'kXerox']}
        result = Builder.from_cli(['-F', 'kDefinition', 'kXerox']).config
        self.assertDictContainsSubset(expectedIn, result, msg="Accepts multiple fields.")

        expectedIn = {'fields': ['kDefinition', 'kXerox'], 'destination': 'data/ha.csv'}
        result = Builder.from_cli(['-F', 'kDefinition', 'kXerox', '-d', 'data/ha.csv']).config
        self.assertDictContainsSubset(expectedIn, result, msg="Accepts multiple arguments.")

    def test_cli_exit_emessage_to_stderr(self):
        """Sends exception .message to stderr on exit."""

        with self.assertRaisesRegexp(SystemExit, 'Field sdfa not found in file list.'):
            with captureStdErr(Builder.from_cli, ['-d', 'data/output.csv', '-F', 'sdfa']) as output:
                pass


def suite():
    setup_path()
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(UnihanHelperFunctions))
    suite.addTest(unittest.makeSuite(UnihanScriptsTestCase))
    suite.addTest(unittest.makeSuite(ProcessTestCase))
    suite.addTest(unittest.makeSuite(CliArgTestCase))
    return suite
