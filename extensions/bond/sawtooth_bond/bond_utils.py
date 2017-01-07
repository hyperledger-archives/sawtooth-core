# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import fractions


def bondprice_to_float(bondprice):
    """

    Args:
        bondprice: str, in the format '92-5+' or '89-5 1/8'
         where the + and trailing fraction are optional.
         Can deal with both '89' and '89-0'
         Will raise errors on '85+', '86-45'

    Returns: float

    """
    args = bondprice.split("-")
    if not (len(args) == 2 or len(args) == 1):
        raise Exception("{} is not formatted correctly".format(bondprice))
    if len(args) == 1:
        try:
            return float(args[0])
        except ValueError:
            raise Exception("{} is not formatted correctly".format(bondprice))
    else:
        whole = float(args[0])
        remainder = 0.0
        if "/" in args[1]:
            tick_n_half_tick, frac = args[1].split(" ")

            num, denom = frac.split("/")
            remainder = float(num) / float(denom)
        else:
            tick_n_half_tick = args[1]

        if "+" in tick_n_half_tick:
            num_ticks = float(tick_n_half_tick.replace("+", ""))
            if num_ticks >= 32:
                raise Exception(
                    "{} is not formatted correctly".format(bondprice))
            num_ticks += .5
        else:
            num_ticks = float(tick_n_half_tick)

        return whole + float((num_ticks + remainder) / 32.0)


def float_to_bondprice(fpn):
    """

    Args:
        fpn: float

    Returns: str, in the form '84-5+' or '98-2 1/8'. The + and trailing
    fraction are mutually exclusive and optional but the
    tick isn't. So 85 isn't valid but 85-0 is. Also, the tick must be less
    than 32 so 78-32 isn't valid

    """
    whole = int(fpn)
    rest = fpn - whole
    num_ticks = 0
    thirty_seconds = 0.0
    while thirty_seconds <= rest - 1 / 32.0:
        num_ticks += 1
        thirty_seconds += 1 / 32.0
    rest = rest - thirty_seconds
    bondprice = "{}-{}".format(whole, num_ticks)
    if rest > 0.0:
        if is_close(rest, 1 / 64.0):
            bondprice += "+"
        else:

            frac = fractions.Fraction(rest * 32)
            bondprice += " {}/{}".format(frac.numerator, frac.denominator)

    return bondprice


def is_close(float_a, float_b, rel_tol=1e-09, abs_tol=0.0):
    """
    Used for equality comparison of floats
    Args:
        float_a: float
        float_b: float
        rel_tol: float
        abs_tol: float

    Returns: boolean

    """
    return abs(float_a - float_b) <= \
        max(rel_tol * max(abs(float_a), abs(float_b)), abs_tol)
