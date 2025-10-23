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
from os.path import dirname, isdir, join, realpath, relpath, splitext
from pathlib import Path
from pprint import pformat
from unicodedata import category, normalize

try:
    import hypothesis.strategies as st
    from hypothesis import Verbosity, assume, given, settings

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
EXPECTED_FAILURES = {}


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
        for language in sorted(LANGUAGES.keys()):
            postfix = "-" + language.lower()
            if encoding.endswith(postfix):
                encoding = encoding.rpartition(postfix)[0]
                break
        # Skip directories for encodings we don't handle yet.
        if encoding in MISSING_ENCODINGS:
            continue
        # Test encoding detection for each file we have of encoding for
        for file_name in listdir(path):
            ext = splitext(file_name)[1].lower()
            if ext not in [".html", ".txt", ".xml", ".srt"]:
                continue
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
    expected_unicode = normalize("NFKD", expected_unicode)
    detected_unicode = normalize("NFKD", detected_unicode)
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

    class JustALengthIssue(Exception):
        pass

    @pytest.mark.xfail
    @given(  # type: ignore[reportPossiblyUnboundVariable]
        st.text(min_size=1),  # type: ignore[reportPossiblyUnboundVariable]
        st.sampled_from([  # type: ignore[reportPossiblyUnboundVariable]
            "ascii",
            "utf-8",
            "utf-16",
            "utf-32",
            "iso-8859-7",
            "iso-8859-8",
            "windows-1255",
        ]),
        st.randoms(),  # type: ignore[reportPossiblyUnboundVariable]
    )
    @settings(max_examples=200)  # type: ignore[reportPossiblyUnboundVariable]
    def test_never_fails_to_detect_if_there_is_a_valid_encoding(txt, enc, rnd):
        try:
            data = txt.encode(enc)
        except UnicodeEncodeError:
            assume(False)  # type: ignore[reportPossiblyUnboundVariable]
            data = b""
        detected = chardet.detect(data)["encoding"]
        if detected is None:
            with pytest.raises(JustALengthIssue):

                @given(st.text(), random=rnd)  # type: ignore[reportPossiblyUnboundVariable]
                @settings(verbosity=Verbosity.quiet, max_examples=50)  # type: ignore[reportPossiblyUnboundVariable]
                def string_poisons_following_text(suffix):
                    try:
                        extended = (txt + suffix).encode(enc)
                    except UnicodeEncodeError:
                        assume(False)  # type: ignore[reportPossiblyUnboundVariable]
                        extended = b""
                    result = chardet.detect(extended)
                    if result and result["encoding"] is not None:
                        raise JustALengthIssue()

    @pytest.mark.xfail
    @given(  # type: ignore[reportPossiblyUnboundVariable]
        st.text(min_size=100),  # type: ignore[reportPossiblyUnboundVariable]
        st.sampled_from(  # type: ignore[reportPossiblyUnboundVariable]
            [
                "ascii",
                "utf-8",
                "utf-16",
                "utf-32",
                "iso-8859-7",
                "iso-8859-8",
                "windows-1255",
            ]
        ),
        st.randoms(),  # type: ignore[reportPossiblyUnboundVariable]
    )
    @settings(max_examples=200)  # type: ignore[reportPossiblyUnboundVariable]
    def test_detect_all_and_detect_one_should_agree(txt, enc, _):
        result = {}
        results = []
        try:
            data = txt.encode(enc)
        except UnicodeEncodeError:
            assume(False)  # type: ignore[reportPossiblyUnboundVariable]
            data = b""
        try:
            result = chardet.detect(data)
            results = chardet.detect_all(data)
            assert result["encoding"] == results[0]["encoding"]
        except Exception as exc:
            raise RuntimeError(f"{result} != {results}") from exc
