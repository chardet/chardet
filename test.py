"""
Run chardet on a bunch of documents and see that we get the correct encodings.

:author: Dan Blanchard
:author: Ian Cordasco
"""

import codecs
import sys
import textwrap
from difflib import ndiff
from os import listdir
from os.path import dirname, isdir, join, realpath, relpath
from pathlib import Path
from pprint import pformat
from unicodedata import category, normalize

try:
    import hypothesis.strategies as st
    from hypothesis import assume, given, settings

    HAVE_HYPOTHESIS = True
except ImportError:
    HAVE_HYPOTHESIS = False
import pytest  # type: ignore[reportMissingImports]

import chardet
from chardet import escsm, mbcssm
from chardet.codingstatemachine import CodingStateMachine
from chardet.enums import MachineState
from chardet.metadata.languages import LANGUAGES

MISSING_ENCODINGS = set()
EXPECTED_FAILURES = {
    # TIS-620 vs CP874 confusion (very similar Thai encodings)
    "tests/TIS-620/pharmacy.kku.ac.th.centerlab.xml",
    "tests/TIS-620/pharmacy.kku.ac.th.healthinfo-ne.xml",
    # MacRoman confusion
    "tests/MacRoman/ioreg_output.txt",
    # Windows-1251 vs MacCyrillic confusion (similar Cyrillic encodings)
    "tests/windows-1251-russian/greek.ru.xml",
    "tests/windows-1251-russian/aug32.hole.ru.xml",
    "tests/MacCyrillic/aug32.hole.ru.xml",
    # ISO-8859-7 vs WINDOWS-1253 confusion (similar Greek encodings)
    "tests/iso-8859-7-greek/disabled.gr.xml",
    "tests/iso-8859-7-greek/naftemporiki.gr.bus.xml",
    "tests/iso-8859-7-greek/naftemporiki.gr.cmm.xml",
    "tests/iso-8859-7-greek/naftemporiki.gr.mrk.xml",
    "tests/iso-8859-7-greek/naftemporiki.gr.spo.xml",
    "tests/iso-8859-7-greek/naftemporiki.gr.wld.xml",
}
MULTI_BYTE_LANGUAGES = {
    "Chinese",
    "Japanese",
    "Korean",
    "Taiwanese",
}


def gen_test_params():
    """Yields tuples of paths and encodings to use for test_encoding_detection"""
    base_path = relpath(join(dirname(realpath(__file__)), "tests"))
    for encoding in listdir(base_path):
        path = join(base_path, encoding)
        # Skip files in tests directory
        if not isdir(path):
            continue
        # Remove language suffixes from encoding if present
        encoding = encoding.lower()
        for language in sorted(set(LANGUAGES.keys()) | MULTI_BYTE_LANGUAGES):
            postfix = "-" + language.lower()
            if encoding.endswith(postfix):
                encoding = encoding.rpartition(postfix)[0]
                break
        # Skip directories for encodings we don't handle yet.
        if encoding in MISSING_ENCODINGS:
            continue
        # Test encoding detection for each file we have of encoding for
        for file_name in listdir(path):
            full_path = join(path, file_name)
            test_case = full_path, encoding
            # Normalize path to use forward slashes for comparison with EXPECTED_FAILURES
            # (which uses forward slashes) to ensure it works on Windows
            if Path(full_path).as_posix() in EXPECTED_FAILURES:
                test_case = pytest.param(*test_case, marks=pytest.mark.xfail)
            yield test_case


@pytest.mark.parametrize("file_name, encoding", gen_test_params())
def test_encoding_detection(file_name, encoding):
    with open(file_name, "rb") as f:
        input_bytes = f.read()
        result = chardet.detect(input_bytes)
        try:
            expected_unicode = input_bytes.decode(encoding)
        except LookupError:
            expected_unicode = ""
        try:
            detected_unicode = input_bytes.decode(result["encoding"])  # type: ignore[reportArgumentType]
        except (LookupError, UnicodeDecodeError, TypeError):
            detected_unicode = ""
    if result:
        encoding_match = (result["encoding"] or "").lower() == encoding
    else:
        encoding_match = False
    # Only care about mismatches that would actually result in different
    # behavior when decoding
    expected_unicode = normalize("NFKC", expected_unicode)
    detected_unicode = normalize("NFKC", detected_unicode)
    if not encoding_match and expected_unicode != detected_unicode:
        wrapped_expected = "\n".join(textwrap.wrap(expected_unicode, 100)) + "\n"
        wrapped_detected = "\n".join(textwrap.wrap(detected_unicode, 100)) + "\n"
        diff = "".join(
            [
                line
                for line in ndiff(
                    wrapped_expected.splitlines(True), wrapped_detected.splitlines(True)
                )
                if not line.startswith(" ")
            ][:20]
        )
        all_encodings = chardet.detect_all(input_bytes, ignore_threshold=True)
    else:
        diff = ""
        encoding_match = True
        all_encodings = [result]
    assert encoding_match, (
        f"Expected {encoding}, but got {result} for {file_name}.  First 20 "
        f"lines with character differences: \n{diff}\n"
        f"All encodings: {pformat(all_encodings)}"
    )


@pytest.mark.parametrize("file_name, encoding", gen_test_params())
def test_encoding_detection_rename_legacy(file_name, encoding):
    with open(file_name, "rb") as f:
        input_bytes = f.read()
        result = chardet.detect(input_bytes, should_rename_legacy=True)
        try:
            expected_unicode = input_bytes.decode(encoding)
        except LookupError:
            expected_unicode = ""
        try:
            detected_unicode = input_bytes.decode(result["encoding"])  # type: ignore[reportArgumentType]
        except (LookupError, UnicodeDecodeError, TypeError):
            detected_unicode = ""
    if result:
        encoding_match = (result["encoding"] or "").lower() == encoding
    else:
        encoding_match = False
    # Only care about mismatches that would actually result in different
    # behavior when decoding
    expected_unicode = normalize("NFKC", expected_unicode)
    detected_unicode = normalize("NFKC", detected_unicode)
    if not encoding_match and expected_unicode != detected_unicode:
        wrapped_expected = "\n".join(textwrap.wrap(expected_unicode, 100)) + "\n"
        wrapped_detected = "\n".join(textwrap.wrap(detected_unicode, 100)) + "\n"
        diff = "".join(
            [
                line
                for line in ndiff(
                    wrapped_expected.splitlines(True), wrapped_detected.splitlines(True)
                )
                if not line.startswith(" ")
            ][:20]
        )
        all_encodings = chardet.detect_all(
            input_bytes, ignore_threshold=True, should_rename_legacy=True
        )
    else:
        diff = ""
        encoding_match = True
        all_encodings = [result]
    assert encoding_match, (
        f"Expected {encoding}, but got {result} for {file_name}.  First 20 "
        f"lines of character differences: \n{diff}\n"
        f"All encodings: {pformat(all_encodings)}"
    )


# TODO add fixtures for non-supported encodings
STATE_MACHINE_MODELS = [
    mbcssm.BIG5_SM_MODEL,
    mbcssm.CP949_SM_MODEL,
    mbcssm.EUCJP_SM_MODEL,
    mbcssm.EUCKR_SM_MODEL,
    # mbcssm.EUCTW_SM_MODEL,
    mbcssm.JOHAB_SM_MODEL,
    mbcssm.GB2312_SM_MODEL,
    mbcssm.SJIS_SM_MODEL,
    # mbcssm.UCS2BE_SM_MODEL,
    # mbcssm.UCS2LE_SM_MODEL,
    # mbcssm.UTF8_SM_MODEL,
    escsm.HZ_SM_MODEL,
    # escsm.ISO2022CN_SM_MODEL,
    escsm.ISO2022JP_SM_MODEL,
    escsm.ISO2022KR_SM_MODEL,
]


def gen_all_chars_unicode():
    """Returns all chars in unicode, except control chars"""
    all_chars = [chr(i) for i in range(0, sys.maxunicode)]
    excluded_categories = set(("Cc", "Cf", "Cn", "Co", "Cs"))

    return [char for char in all_chars if category(char) not in excluded_categories]


@pytest.mark.parametrize(
    "state_machine_model", STATE_MACHINE_MODELS, ids=lambda model: model["name"]
)
def test_coding_state_machine(state_machine_model):
    state_machine = CodingStateMachine(state_machine_model)
    encoding_name = state_machine_model["name"]
    unicode_all_chars = gen_all_chars_unicode()

    for char in unicode_all_chars:
        encoded_chars = codecs.encode(char, encoding_name, errors="ignore")

        for encoded_char in encoded_chars:
            state = state_machine.next_state(encoded_char)

            if state == MachineState.ERROR:
                error_message = "Failed to encode Unicode %s, Encoding: %s" % (
                    hex(ord(char)),
                    ",".join([hex(encoded_char) for encoded_char in encoded_chars]),
                )
                raise Exception(error_message)


if HAVE_HYPOTHESIS:

    @given(  # type: ignore[reportPossiblyUnboundVariable]
        st.text(min_size=20),  # type: ignore[reportPossiblyUnboundVariable]
        st.sampled_from([  # type: ignore[reportPossiblyUnboundVariable]
            "ascii",
            "utf-8",
            "utf-16",
            "utf-32",
            "iso-8859-7",
            "iso-8859-8",
            "windows-1255",
        ]),
    )
    @settings(max_examples=200)  # type: ignore[reportPossiblyUnboundVariable]
    def test_never_returns_none_for_valid_encoding(txt, enc):
        """
        Test that detect() returns an encoding for sufficiently long validly-encoded data.

        With enough data (20+ characters), chardet should be able to make a determination
        and not return None. The detected encoding may not always match the original
        encoding (e.g., ASCII might be detected as UTF-8), but it should be decodable.
        """
        try:
            data = txt.encode(enc)
        except UnicodeEncodeError:
            assume(False)  # type: ignore[reportPossiblyUnboundVariable]
            return

        result = chardet.detect(data)

        # Should return an encoding for data with sufficient length
        assert result["encoding"] is not None, (
            f"detect() returned None for {len(data)} bytes of valid {enc} data. "
            f"Data: {data[:100]!r}{'...' if len(data) > 100 else ''}"
        )

        # Verify the detected encoding can actually decode the data
        if result["encoding"]:
            try:
                data.decode(result["encoding"])
            except (UnicodeDecodeError, LookupError):
                # It's okay if decoding fails - encodings can overlap
                # The important thing is we returned something
                pass

    @given(  # type: ignore[reportPossiblyUnboundVariable]
        st.text(min_size=100),  # type: ignore[reportPossiblyUnboundVariable]
        st.sampled_from([  # type: ignore[reportPossiblyUnboundVariable]
            "ascii",
            "utf-8",
            "utf-16",
            "utf-32",
            "iso-8859-7",
            "iso-8859-8",
            "windows-1255",
        ]),
    )
    @settings(max_examples=200, deadline=None)  # type: ignore[reportPossiblyUnboundVariable]
    def test_detect_all_and_detect_one_should_agree(txt, enc):
        """
        Test that detect() and detect_all() return consistent results.

        The first result from detect_all() should match detect() when both
        use the same confidence threshold.
        """
        try:
            data = txt.encode(enc)
        except UnicodeEncodeError:
            assume(False)  # type: ignore[reportPossiblyUnboundVariable]
            return

        result = chardet.detect(data)
        results = chardet.detect_all(data)

        # Both should return the same encoding for the top result
        assert result["encoding"] == results[0]["encoding"], (
            f"detect() returned {result['encoding']} but detect_all()[0] "
            f"returned {results[0]['encoding']} for {len(data)} bytes of {enc}"
        )
