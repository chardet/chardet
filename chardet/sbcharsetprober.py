######################## BEGIN LICENSE BLOCK ########################
# The Original Code is Mozilla Universal charset detector code.
#
# The Initial Developer of the Original Code is
# Netscape Communications Corporation.
# Portions created by the Initial Developer are Copyright (C) 2001
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Mark Pilgrim - port to Python
#   Shy Shalom - original C code
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301  USA
######################### END LICENSE BLOCK #########################

from .charsetprober import CharSetProber
from .compat import wrap_ord
from .enums import ProbingState


class SingleByteCharSetProber(CharSetProber):
    SAMPLE_SIZE = 64
    SB_ENOUGH_REL_THRESHOLD = 1024
    POSITIVE_SHORTCUT_THRESHOLD = 0.95
    NEGATIVE_SHORTCUT_THRESHOLD = 0.05
    SYMBOL_CAT_ORDER = 250
    NUMBER_OF_SEQ_CAT = 4
    POSITIVE_CAT = NUMBER_OF_SEQ_CAT - 1

    def __init__(self, model, reversed=False, name_prober=None):
        super(SingleByteCharSetProber, self).__init__()
        self._model = model
        # TRUE if we need to reverse every pair in the model lookup
        self._reversed = reversed
        # Optional auxiliary prober for name decision
        self._name_prober = name_prober
        self._last_order = None
        self._seq_counters = None
        self._total_seqs = None
        self._total_char = None
        self._freq_char = None
        self.reset()

    def reset(self):
        super(SingleByteCharSetProber, self).reset()
        # char order of last character
        self._last_order = 255
        self._seq_counters = [0] * self.NUMBER_OF_SEQ_CAT
        self._total_seqs = 0
        self._total_char = 0
        # characters that fall in our sampling range
        self._freq_char = 0

    @property
    def charset_name(self):
        if self._name_prober:
            return self._name_prober.charset_name
        else:
            return self._model['charset_name']

    def feed(self, byte_str):
        if not self._model['keep_english_letter']:
            byte_str = self.filter_international_words(byte_str)
        num_bytes = len(byte_str)
        if not num_bytes:
            return self.state
        for c in byte_str:
            order = self._model['char_to_order_map'][wrap_ord(c)]
            if order < self.SYMBOL_CAT_ORDER:
                self._total_char += 1
            if order < self.SAMPLE_SIZE:
                self._freq_char += 1
                if self._last_order < self.SAMPLE_SIZE:
                    self._total_seqs += 1
                    if not self._reversed:
                        i = (self._last_order * self.SAMPLE_SIZE) + order
                        model = self._model['precedence_matrix'][i]
                    else:  # reverse the order of the letters in the lookup
                        i = (order * self.SAMPLE_SIZE) + self._last_order
                        model = self._model['precedence_matrix'][i]
                    self._seq_counters[model] += 1
            self._last_order = order

        if self.state == ProbingState.detecting:
            if self._total_seqs > self.SB_ENOUGH_REL_THRESHOLD:
                cf = self.get_confidence()
                if cf > self.POSITIVE_SHORTCUT_THRESHOLD:
                    self.logger.debug('%s confidence = %s, we have a winner',
                                      self._model['charset_name'], cf)
                    self._state = ProbingState.found_it
                elif cf < self.NEGATIVE_SHORTCUT_THRESHOLD:
                    self.logger.debug('%s confidence = %s, below negative '
                                      'shortcut threshhold %s',
                                      self._model['charset_name'], cf,
                                      self.NEGATIVE_SHORTCUT_THRESHOLD)
                    self._state = ProbingState.not_me

        return self.state

    def get_confidence(self):
        r = 0.01
        if self._total_seqs > 0:
            r = ((1.0 * self._seq_counters[self.POSITIVE_CAT]) / self._total_seqs
                 / self._model['typical_positive_ratio'])
            r = r * self._freq_char / self._total_char
            if r >= 1.0:
                r = 0.99
        return r
