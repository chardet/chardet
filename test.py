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
from chardet.encoding_eras import get_encoding_era
from chardet.enums import MachineState
from chardet.metadata.languages import LANGUAGES
from chardet.universaldetector import UniversalDetector

MISSING_ENCODINGS = set()
EXPECTED_FAILURES = {
    # EBCDIC encodings are archaic mainframe formats that are inherently
    # ambiguous and confuse each other. These failures are expected.
    # CP037 (US EBCDIC) vs CP500 (International EBCDIC) vs other EBCDIC variants
    "tests/cp037-english/_ude_1.txt",
    "tests/cp037-english/culturax_mC4_84513.txt",
    "tests/cp500-english/culturax_mC4_84512.txt",
    "tests/cp500-english/culturax_mC4_84513.txt",
    # CP1026 (Turkish EBCDIC) confusion
    "tests/cp1026-turkish/culturax_mC4_107848.txt",
    # CP424 (Hebrew EBCDIC) confused with other encodings
    "tests/cp424-hebrew/_ude_1.txt",
    "tests/cp424-hebrew/culturax_OSCAR-2301_58265.txt",
    "tests/cp424-hebrew/culturax_OSCAR-2301_58267.txt",
    "tests/cp424-hebrew/culturax_OSCAR-2301_58268.txt",
    # Legacy encoding ambiguities (Mac vs DOS vs ISO)
    # These are inherently ambiguous and cannot be reliably distinguished
    "tests/maclatin2-czech/culturax_OSCAR-2019_98821.txt",
    "tests/macturkish-turkish/culturax_mC4_107848.txt",
    "tests/iso-8859-3-turkish/culturax_mC4_107848.txt",
    "tests/cp852-czech/culturax_OSCAR-2019_98821.txt",
    "tests/cp720-arabic/culturax_OSCAR-2109_98639.txt",
    "tests/iso-8859-6-arabic/_chromium_windows-1256_with_no_encoding_specified.html",
    # Hungarian: ISO-8859-2 vs ISO-8859-16 ambiguities
    # Both encodings are very similar for Hungarian, differing in a few characters
    "tests/iso-8859-2-hungarian/_ude_1.txt",
    "tests/iso-8859-2-hungarian/_ude_2.txt",
    "tests/iso-8859-2-hungarian/_ude_3.txt",
    "tests/iso-8859-2-hungarian/honositomuhely.hu.xml",
    "tests/iso-8859-2-hungarian/bbc.co.uk.hu.learningenglish.xml",
    "tests/windows-1250-hungarian/bbc.co.uk.hu.pressreview.xml",
    # Greek: ISO-8859-7 vs Windows-1253 ambiguities
    # Both encodings are very similar for Greek text
    "tests/iso-8859-7-greek/culturax_mC4_103810.txt",
    "tests/iso-8859-7-greek/disabled.gr.xml",
    "tests/iso-8859-7-greek/naftemporiki.gr.mrk.xml",
    "tests/iso-8859-7-greek/naftemporiki.gr.spo.xml",
    "tests/windows-1253-greek/culturax_mC4_103810.txt",
    # Turkish: ISO-8859-9 vs ISO-8859-15 ambiguity on short files
    # Very short files lack sufficient distinguishing features
    "tests/iso-8859-9-turkish/divxplanet.com.xml",
    # Hungarian ISO-8859-2 vs ISO-8859-16 ambiguity on sampled large file
    "tests/iso-8859-2-hungarian/torokorszag.blogspot.com.xml",
    # File with only 1 high byte in 748KB (99.9998% ASCII)
    # Sampling may miss the single non-ASCII character
    "tests/iso-8859-1-english/ioreg_output.txt",
    # UTF-16 without BOM: Files with >95% non-ASCII CJK characters
    # These have too few null bytes (<5%) for reliable UTF-16 pattern detection
    "tests/utf-16le-japanese/culturax_mC4_5.txt",
    "tests/utf-16be-japanese/culturax_mC4_5.txt",
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


@pytest.mark.timeout(7)
@pytest.mark.parametrize("file_name, encoding", gen_test_params())
def test_encoding_detection(file_name, encoding):
    # Determine which era is needed for this encoding
    era = get_encoding_era(encoding)

    with open(file_name, "rb") as f:
        input_bytes = f.read()
        result = chardet.detect(input_bytes, encoding_era=era)
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
            input_bytes, ignore_threshold=True, encoding_era=era
        )
    else:
        diff = ""
        encoding_match = True
        all_encodings = [result]
    assert encoding_match, (
        f"Expected {encoding}, but got {result} for {file_name}.  First 20 "
        f"lines with character differences: \n{diff}\n"
        f"All encodings: {pformat(all_encodings)}"
    )


@pytest.mark.timeout(7)
@pytest.mark.parametrize("file_name, encoding", gen_test_params())
def test_encoding_detection_rename_legacy(file_name, encoding):
    # Determine which era is needed for this encoding
    era = get_encoding_era(encoding)

    with open(file_name, "rb") as f:
        input_bytes = f.read()
        result = chardet.detect(
            input_bytes, should_rename_legacy=True, encoding_era=era
        )
        try:
            expected_unicode = input_bytes.decode(encoding)
        except LookupError:
            expected_unicode = ""
        try:
            detected_unicode = input_bytes.decode(result["encoding"])  # type: ignore[reportArgumentType]
        except (LookupError, UnicodeDecodeError, TypeError):
            detected_unicode = ""
    if result:
        detected_encoding = (result["encoding"] or "").lower()
        encoding_match = detected_encoding == encoding

        # Check if the detected encoding is a valid renamed version via LEGACY_MAP
        if not encoding_match and encoding in UniversalDetector.LEGACY_MAP:
            expected_renamed = UniversalDetector.LEGACY_MAP[encoding].lower()
            if detected_encoding == expected_renamed:
                encoding_match = True
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
            input_bytes,
            ignore_threshold=True,
            should_rename_legacy=True,
            encoding_era=era,
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


STATE_MACHINE_MODELS = [
    mbcssm.BIG5_SM_MODEL,
    mbcssm.CP949_SM_MODEL,
    mbcssm.EUCJP_SM_MODEL,
    mbcssm.EUCKR_SM_MODEL,
    mbcssm.JOHAB_SM_MODEL,
    mbcssm.GB18030_SM_MODEL,  # GB2312 removed - GB18030 is superset
    mbcssm.SJIS_SM_MODEL,
    mbcssm.UTF8_SM_MODEL,
    escsm.HZ_SM_MODEL,
    escsm.ISO2022JP_SM_MODEL,
    escsm.ISO2022KR_SM_MODEL,
]


@pytest.mark.parametrize(
    "state_machine_model", STATE_MACHINE_MODELS, ids=lambda model: model["name"]
)
def test_coding_state_machine_valid_characters(state_machine_model):
    """
    Test that state machines accept all valid characters for their encoding.

    State machines should never enter ERROR state when processing valid byte
    sequences. ASCII characters (0x00-0x7F) should stay in or return to START
    state since they're valid single-byte sequences in multi-byte encodings.
    Multi-byte sequences should transition through intermediate states and
    return to START upon completion.
    """
    state_machine = CodingStateMachine(state_machine_model)
    encoding_name = state_machine_model["name"]
    all_non_control_codepoints = [
        chr(i) for i in range(0, sys.maxunicode) if not category(chr(i)).startswith("C")
    ]

    for codepoint in all_non_control_codepoints:
        try:
            encoded_bytes = codecs.encode(codepoint, encoding_name)
        except (LookupError, UnicodeEncodeError):
            # Encoding not supported or character not representable in this encoding
            continue

        state_machine.reset()
        state = MachineState.START
        for i, encoded_byte in enumerate(encoded_bytes):
            state = state_machine.next_state(encoded_byte)

            assert state != MachineState.ERROR, (
                f"{encoding_name} state machine entered ERROR state for Unicode "
                f"{codepoint!r} ({hex(ord(codepoint))}) represented by the bytes "
                f"{encoded_bytes!r} at byte {encoded_byte!r} (index {i})"
            )

        # After processing all bytes, should be back in START state (complete sequence)
        assert state == MachineState.START or state == MachineState.ITS_ME, (
            f"{encoding_name} state machine ended in unexpected state {state} for Unicode "
            f"{codepoint!r} ({hex(ord(codepoint))}) represented by the bytes "
            f"{encoded_bytes!r}. Expected START (complete sequence) or ITS_ME (definitive match)."
        )


@pytest.mark.parametrize(
    "state_machine_model,invalid_sequence,description",
    [
        # UTF-8 invalid sequences
        (mbcssm.UTF8_SM_MODEL, [0xC0, 0x80], "Overlong encoding of NULL"),
        (mbcssm.UTF8_SM_MODEL, [0xFF], "Invalid start byte 0xFF"),
        (mbcssm.UTF8_SM_MODEL, [0xFE], "Invalid start byte 0xFE"),
        (mbcssm.UTF8_SM_MODEL, [0xC2], "Incomplete 2-byte sequence"),
        (mbcssm.UTF8_SM_MODEL, [0xE0], "Incomplete 3-byte sequence"),
        (mbcssm.UTF8_SM_MODEL, [0xF0], "Incomplete 4-byte sequence"),
        (mbcssm.UTF8_SM_MODEL, [0xC2, 0x00], "Invalid continuation byte"),
        # EUC-JP
        (mbcssm.EUCJP_SM_MODEL, [0xA1], "Incomplete 2-byte sequence"),
        # EUC-KR
        (mbcssm.EUCKR_SM_MODEL, [0xA1], "Incomplete 2-byte sequence"),
        # GB18030 (GB2312 removed - GB18030 is superset)
        (mbcssm.GB18030_SM_MODEL, [0x81], "Incomplete 2-byte sequence"),
        # Shift_JIS
        (mbcssm.SJIS_SM_MODEL, [0x81], "Incomplete 2-byte sequence"),
        # Big5
        (mbcssm.BIG5_SM_MODEL, [0xA1], "Incomplete 2-byte sequence"),
        # CP949
        (mbcssm.CP949_SM_MODEL, [0x81], "Incomplete 2-byte sequence"),
        # Johab
        (mbcssm.JOHAB_SM_MODEL, [0x84], "Incomplete 2-byte sequence"),
    ],
    ids=[
        "UTF-8-Overlong encoding of NULL",
        "UTF-8-Invalid start byte 0xFF",
        "UTF-8-Invalid start byte 0xFE",
        "UTF-8-Incomplete 2-byte sequence",
        "UTF-8-Incomplete 3-byte sequence",
        "UTF-8-Incomplete 4-byte sequence",
        "UTF-8-Invalid continuation byte",
        "EUC-JP-Incomplete 2-byte sequence",
        "EUC-KR-Incomplete 2-byte sequence",
        "GB18030-Incomplete 2-byte sequence",
        "Shift_JIS-Incomplete 2-byte sequence",
        "Big5-Incomplete 2-byte sequence",
        "CP949-Incomplete 2-byte sequence",
        "Johab-Incomplete 2-byte sequence",
    ],
)
def test_coding_state_machine_invalid_sequences(
    state_machine_model, invalid_sequence, description
):
    """
    Test that state machines reject invalid byte sequences.

    This test verifies that invalid byte sequences cause the state
    machine to either enter ERROR state or remain in a non-START state
    (for incomplete sequences).
    """
    state_machine = CodingStateMachine(state_machine_model)
    encoding_name = state_machine_model["name"]
    state_machine.reset()
    final_state = MachineState.START

    for byte in invalid_sequence:
        final_state = state_machine.next_state(byte)

    # For incomplete sequences, we expect either ERROR or not START
    # (since a complete sequence should return to START)
    if len(invalid_sequence) == 1 and invalid_sequence[0] >= 0x80:
        # Single high byte should leave us in non-START state or ERROR
        assert final_state != MachineState.START, (
            f"{encoding_name} state machine returned to START for incomplete "
            f"sequence {invalid_sequence!r} ({description}), expected non-START state"
        )


# State machine models that support comprehensive invalid sequence testing
# (excludes stateful encodings like ISO-2022 and HZ that use escape sequences)
TESTABLE_STATE_MACHINE_MODELS = [
    (mbcssm.GB18030_SM_MODEL, "gb18030"),
    (mbcssm.UTF8_SM_MODEL, "utf-8"),
]


@pytest.mark.parametrize(
    "state_machine_model,python_codec",
    TESTABLE_STATE_MACHINE_MODELS,
    ids=[model["name"] for model, _ in TESTABLE_STATE_MACHINE_MODELS],
)
def test_coding_state_machine_rejects_all_invalid_sequences(
    state_machine_model, python_codec
):
    """
    Generative test that state machines properly reject ALL invalid byte sequences.

    This test generates all possible byte sequences up to the maximum character
    length for the encoding and verifies that sequences which Python's strict
    decoder rejects are NOT accepted by the state machine (i.e., do not return
    to START or ITS_ME state, indicating successful decoding).

    The goal is to ensure state machines don't accept byte sequences that are
    invalid according to the encoding specification. Invalid sequences should
    either:
    - Enter ERROR state (definitively invalid)
    - Stay in an intermediate state (incomplete sequence)
    - Never return to START/ITS_ME (which indicates a complete valid sequence)

    Optimizations to avoid timeout:
    - Only tests sequences starting with high bytes (0x80+) since ASCII is always valid
    - Limits to 100,000 test cases for encodings with large search spaces
    - Skips stateful encodings (ISO-2022, HZ) that require escape sequences
    """
    import itertools

    state_machine = CodingStateMachine(state_machine_model)
    encoding_name = state_machine_model["name"]

    # Find maximum character length for this encoding
    char_len_table = state_machine_model["char_len_table"]
    max_len = max(char_len_table)

    if max_len == 0:
        # Stateful encoding, skip (requires escape sequences)
        pytest.skip(f"{encoding_name} is stateful and requires escape sequences")

    # Track statistics and issues
    invalid_count = 0
    tested_count = 0
    issues = []

    for length in range(1, max_len + 1):
        # Only generate sequences starting with high bytes (0x80-0xFF)
        # as ASCII (0x00-0x7F) is always valid in these encodings
        for byte_tuple in itertools.product(range(0x80, 0x100), repeat=length):
            tested_count += 1
            byte_sequence = bytes(byte_tuple)

            # Try to decode with Python's codec using strict error handling
            try:
                byte_sequence.decode(python_codec, errors="strict")
                is_valid_in_python = True
            except UnicodeDecodeError:
                is_valid_in_python = False
                invalid_count += 1

            # Test state machine
            state_machine.reset()
            final_state = MachineState.START

            for byte_val in byte_sequence:
                final_state = state_machine.next_state(byte_val)

            # If Python's strict decoder rejects the sequence, the state machine
            # must NOT accept it as a complete valid sequence
            if not is_valid_in_python and final_state in (
                MachineState.START,
                MachineState.ITS_ME,
            ):
                issues.append((byte_sequence, final_state))

            # Limit testing to avoid extremely long tests
            # UTF-8 with 4-byte sequences could be 128^4 = 268M combinations
            if tested_count >= 100000:
                break

        if tested_count >= 100000:
            break

    # Assert that no invalid sequences were accepted
    if issues:
        issue_summary = "\n".join(
            f"  {seq.hex()}: ended in state {state.name}" for seq, state in issues[:20]
        )
        if len(issues) > 20:
            issue_summary += f"\n  ... and {len(issues) - 20} more"

        pytest.fail(
            f"{encoding_name} state machine incorrectly accepted {len(issues)} invalid byte "
            f"sequences (out of {invalid_count} total invalid sequences tested).\n"
            f"State machines should reject (ERROR) or leave incomplete (intermediate state) "
            f"invalid sequences, not accept them (START/ITS_ME).\n"
            f"\nFirst invalid sequences that were incorrectly accepted:\n{issue_summary}\n\n"
            f"Total tested: {tested_count} sequences"
        )


@pytest.mark.parametrize(
    "state_machine_model", STATE_MACHINE_MODELS, ids=lambda model: model["name"]
)
def test_coding_state_machine_transitions(state_machine_model):
    """
    Test state machine transition properties.

    Verify that:
    1. Multi-byte sequences transition through intermediate states
    2. Complete sequences return to START or ITS_ME
    3. State machine resets properly
    """
    state_machine = CodingStateMachine(state_machine_model)
    encoding_name = state_machine_model["name"]

    # Find a multi-byte character for this encoding
    multi_byte_char = None
    for codepoint in range(0x80, 0x10000):  # Start at 0x80 to avoid ASCII
        try:
            encoded_bytes = codecs.encode(chr(codepoint), encoding_name)
            if len(encoded_bytes) > 1:
                multi_byte_char = (chr(codepoint), encoded_bytes)
                break
        except (LookupError, UnicodeEncodeError):
            continue

    if multi_byte_char:
        char, encoded_bytes = multi_byte_char
        state_machine.reset()

        states = []
        for encoded_byte in encoded_bytes:
            state = state_machine.next_state(encoded_byte)
            states.append(state)

        # For multi-byte sequences, should see intermediate states
        if len(encoded_bytes) > 1:
            # At least one intermediate state should be non-START (except possibly the last)
            intermediate_states = states[:-1]
            if intermediate_states:
                has_intermediate = any(
                    s != MachineState.START for s in intermediate_states
                )
                assert has_intermediate, (
                    f"{encoding_name} state machine did not transition through intermediate "
                    f"states for multi-byte character {char!r} ({hex(ord(char))}) with bytes "
                    f"{encoded_bytes!r}. States: {states}"
                )

        # Final state should be START or ITS_ME (complete sequence)
        final_state = states[-1]
        assert final_state in (MachineState.START, MachineState.ITS_ME), (
            f"{encoding_name} state machine ended in unexpected state {final_state} for "
            f"character {char!r} with bytes {encoded_bytes!r}"
        )

        # Test reset functionality
        state_machine.reset()
        assert state_machine._curr_state == MachineState.START, (
            f"{encoding_name} state machine did not reset to START state"
        )


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
