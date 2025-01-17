"""
Copyright 2019 Goldman Sachs.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
"""

import logging
from copy import copy
from datetime import date, datetime
from re import search
from typing import Union, Optional, List

import gs_quant.datetime.rules as rules
from gs_quant.errors import MqValueError
from gs_quant.markets import PricingContext
from gs_quant.markets.securities import ExchangeCode
from gs_quant.target.common import Currency

_logger = logging.getLogger(__name__)


class RelativeDate:

    def __init__(self,
                 rule: str,
                 base_date: Optional[date] = None):
        self.rule = rule
        if base_date:
            self.base_date = base_date
        elif PricingContext.current.pricing_date:
            d = PricingContext.current.pricing_date.date() \
                if isinstance(PricingContext.current.pricing_date, datetime) \
                else PricingContext.current.pricing_date
            self.base_date = d
        else:
            self.base_date = date.today()

    def apply_rule(self,
                   currencies: List[Union[Currency, str]] = None,
                   exchanges: List[Union[ExchangeCode, str]] = None,
                   holiday_calendar: List[date] = None,
                   week_mask: str = '1111100') -> date:
        """
        Applies business date logic on the rule using the given holiday calendars for rules that use business
        day logic. week_mask is based off
        https://numpy.org/doc/stable/reference/generated/numpy.busdaycalendar.weekmask.html.

        :param holiday_calendar: Optional list of date to use for holiday calendar. This parameter takes precedence over
        currencies/exchanges.
        :param currencies: List of currency holiday calendars to use. (GS Internal only)
        :param exchanges: List of exchange holiday calendars to use.
        :param week_mask: String of seven-element boolean mask indicating valid days
        :return: dt.date
        """

        result = copy(self.base_date)

        for rule in self._get_rules():
            result = self.__handle_rule(rule, result, week_mask,
                                        currencies=currencies, exchanges=exchanges, holiday_calendar=holiday_calendar)

        return result

    def _get_rules(self) -> List[str]:
        rules = []
        current_rule = ''
        if not len(self.rule):
            raise MqValueError('Invalid Rule ""')
        current_alpha = self.rule[0].isalpha()
        for c in self.rule:
            is_alpha = c.isalpha()
            if current_alpha and not is_alpha:
                if current_rule.startswith('+'):
                    rules.append(current_rule[1:])
                else:
                    rules.append(current_rule)
                current_rule = ''
                current_alpha = False
            if is_alpha:
                current_alpha = True
            current_rule += c
        if current_rule.startswith('+'):
            rules.append(current_rule[1:])
        else:
            rules.append(current_rule)
        return rules

    def __handle_rule(self,
                      rule: str,
                      result: date,
                      week_mask: str,
                      currencies: List[Union[Currency, str]] = None,
                      exchanges: List[Union[ExchangeCode, str]] = None,
                      holiday_calendar: List[date] = None) -> date:
        if rule.startswith('-'):
            number_match = search('\d+', rule[1:])
            number = int(number_match.group(0)) * -1 if number_match else 0
            rule_str = rule[number_match.endpos:]
        else:
            number_match = search('\d+', rule)
            if number_match:
                rule_str = rule[number_match.endpos - 1:]
                number = int(number_match.group(0))
            else:
                rule_str = rule
                number = 0

        if not rule_str:
            raise MqValueError(f'Invalid rule "{rule}"')

        try:
            rule_class = getattr(rules, f'{rule_str}Rule')
            return rule_class(result,
                              results=result,
                              number=number,
                              week_mask=week_mask,
                              currencies=currencies,
                              exchanges=exchanges,
                              holiday_calendar=holiday_calendar).handle()
        except AttributeError:
            raise NotImplementedError(f'Rule {rule} not implemented')
