# Encoding Detection Tie-Breaking Heuristics

Based on research into modern encoding detection algorithms (charset-normalizer, uchardet, etc.), this document outlines potential heuristics for improving detection when confidence scores are very close.

## Currently Implemented Heuristics

### 1. BOM Detection (100% confidence)
- Already implemented in `universaldetector.py`
- Takes precedence over all statistical detection
- Works for UTF-8, UTF-16, UTF-32

### 2. Windows-Specific Byte Detection
- Bytes in 0x80-0x9F range suggest Windows encodings
- Triggers remapping: ISO-8859-1 → Windows-1252, etc.
- **Enhancement**: Now checks if MacRoman is a close contender (within 99.5%) before remapping

### 3. Mac Letter Pattern Detection
- Pattern: `[a-zA-Z][\x80-\x9F][a-zA-Z]` suggests MacRoman
- In 0x80-0x9F, MacRoman has letters while Windows-1252 has punctuation
- Used to distinguish MacRoman vs Windows-1252

### 4. MacRoman vs ISO/Windows Tie-Breaking
- When MacRoman wins but ISO/Windows are within 99.5% confidence
- AND no Mac letter patterns or Windows bytes exist
- Prefer ISO/Windows (handles text using only common chars >0x9F)

### 5. Legacy Encoding Remapping
- Only enabled for `MODERN_WEB` encoding era
- Maps ISO-8859-* to Windows-125* (supersets with more characters)
- Disabled for `LEGACY` era to preserve historical encoding detection

## Proposed Additional Heuristics

### 6. Text Quality Metrics (from charset-normalizer)

**Mess Ratio** - Percentage of "messy" characters in decoded text:
- Invalid Unicode sequences
- Control characters (except common ones like \n, \t)
- Rare/unusual Unicode characters
- Replacement character (�) frequency

**Implementation approach**:
```python
def calculate_mess_ratio(decoded_text: str) -> float:
    """Calculate ratio of problematic characters in decoded text."""
    if not decoded_text:
        return 1.0
    
    messy_count = 0
    for char in decoded_text:
        # Control characters (except whitespace)
        if ord(char) < 32 and char not in '\n\r\t':
            messy_count += 1
        # Replacement character
        elif char == '\ufffd':
            messy_count += 2  # Weight heavily
        # Private use area
        elif 0xE000 <= ord(char) <= 0xF8FF:
            messy_count += 1
            
    return messy_count / len(decoded_text)
```

**Usage in tie-breaking**:
When encodings are within 1% confidence, prefer the one with lower mess ratio.

### 7. Coherence Scoring (simplified)

**Basic coherence checks**:
- Word boundary detection (spaces vs no spaces)
- Repeated character sequences (e.g., "������")
- Language-specific character distribution

**Implementation approach**:
```python
def calculate_coherence_score(decoded_text: str, language: str) -> float:
    """Simple coherence scoring based on text structure."""
    if not decoded_text or len(decoded_text) < 10:
        return 0.5
    
    score = 1.0
    
    # Check for word boundaries (spaces)
    word_count = len(decoded_text.split())
    if word_count < len(decoded_text) / 50:  # Too few spaces
        score *= 0.8
    
    # Check for repeated characters (garbled text indicator)
    max_repeat = max_consecutive_chars(decoded_text)
    if max_repeat > 10:
        score *= 0.5
    
    # Check for mixed scripts (suspicious)
    scripts = detect_scripts(decoded_text)
    if len(scripts) > 2:
        score *= 0.9
        
    return score
```

### 8. Encoding Era and Modernity Preference

**Preference order** (when confidence is within 0.5%):
1. UTF-8 (universal)
2. Windows-125x (modern, widely used)
3. ISO-8859-x (legacy but common)
4. Mac encodings (less common)
5. DOS encodings (CP850, CP437 - very legacy)
6. EBCDIC (CP037, CP500 - mainframe only)

**Implementation**:
```python
ENCODING_PREFERENCE_TIERS = {
    'utf-8': 1,
    'windows-1252': 2, 'windows-1251': 2, 'windows-1250': 2,
    'iso-8859-1': 3, 'iso-8859-2': 3, 'iso-8859-15': 3,
    'macroman': 4, 'maclatin2': 4,
    'cp850': 5, 'cp437': 5, 'cp858': 5,
    'cp037': 6, 'cp500': 6,
}

def get_preference_tier(encoding: str) -> int:
    return ENCODING_PREFERENCE_TIERS.get(encoding.lower(), 999)
```

### 9. Language-Specific Encoding Preference

**Common pairings**:
- Western European: Windows-1252 > ISO-8859-1 > MacRoman
- Central European: Windows-1250 > ISO-8859-2 > MacLatin2
- Cyrillic: Windows-1251 > ISO-8859-5 > MacCyrillic
- Greek: Windows-1253 > ISO-8859-7 > MacGreek

When detected language matches encoding's target language, add small bonus (0.5-1%).

### 10. File Length Penalty for Short Files

For files < 1KB:
- Increase required confidence threshold
- Prefer UTF-8 as safer default
- Be more conservative with EBCDIC/DOS encodings

### 11. Byte Distribution Analysis

**Statistical checks**:
- Null byte ratio (>5% suggests binary or UTF-16/32)
- High-bit ratio (0x80+): <10% suggests ASCII-heavy, favor UTF-8
- Control character frequency
- Byte entropy

### 12. Language Model Confidence Weighting

Current: All language models weighted equally
Proposed: Weight by training data size and quality

```python
LANGUAGE_MODEL_QUALITY = {
    'English': 1.0,   # Large, high-quality training data
    'French': 0.98,
    'German': 0.98,
    'Spanish': 0.98,
    'Irish': 0.85,    # Smaller training corpus
    'Welsh': 0.85,
    'Breton': 0.80,   # Very small training corpus
}
```

Adjust confidence: `adjusted_conf = base_conf * quality_factor`

## Implementation Priority

**High Priority** (Easy wins):
1. ✅ Encoding era/modernity preference (lines of code: ~20)
2. Mess ratio calculation (lines: ~30)
3. File length penalties (lines: ~10)

**Medium Priority**:
4. Basic coherence scoring (lines: ~50)
5. Language-specific encoding preferences (lines: ~30)
6. Byte distribution analysis (lines: ~40)

**Low Priority** (Complex, may need more research):
7. Language model quality weighting (requires retraining)
8. Advanced coherence with NLP models

## Testing Strategy

For each heuristic:
1. Run on current 58 failing tests
2. Measure improvement (failures reduced)
3. Ensure no regressions (2093 passing tests still pass)
4. Document cases where heuristic helps vs doesn't

## References

- charset-normalizer: https://github.com/jawah/charset_normalizer
- Mozilla's chardet: https://chardet.readthedocs.io/
- uchardet: https://www.freedesktop.org/wiki/Software/uchardet/
- ICU charset detection: https://unicode-org.github.io/icu/userguide/conversion/detection.html
