#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 28 13:46:36 2019

@author: annaquinlan
https://github.com/tidepool-org/LoopKit/blob/
57a9f2ba65ae3765ef7baafe66b883e654e08391/LoopKit/CarbKit/CarbMath.swift
"""
# pylint: disable=R0913, C0200, C0301, R0914, R0915
import sys
from datetime import timedelta

from insulin_math import find_ratio_at_time
from date import time_interval_since


def map_(
        carb_entry_starts, carb_entry_quantities, carb_entry_absorptions,
        effect_starts, effect_ends, effect_values,
        carb_ratio_starts, carb_ratios,
        sensitivity_starts, sensitivity_ends, sensitivity_values,
        absorption_time_overrun,
        default_absorption_time,
        delay
        ):
    """
    Maps a sorted timeline of carb entries to the observed absorbed
    carbohydrates for each, from a timeline of glucose effect velocities.

    This makes some important assumptions:
        - insulin effects, used with glucose to calculate
          counteraction, are "correct"
        - carbs are absorbed completely in the order they were eaten
          without mixing or overlapping effects

    Arguments:
    carb_entry_starts -- list of times of carb entry (datetime objects)
    carb_entry_quantities -- list of grams of carbs eaten
    carb_entry_absorptions -- list of lengths of absorption times (mins)

    effect_starts -- list of start times of carb effect (datetime objects)
    effect_ends -- list of end times of carb effect (datetime objects)
    effect_values -- list of carb effects (mg/dL)

    carb_ratio_starts -- list of start times of carb ratios (time objects)
    carb_ratios -- list of carb ratios (G/U)

    Output:
    3 lists in format (absorption_results, absorption_timelines, carb_entries)
        - lists are matched by index
            - one index represents one carb entry and its corresponding data

        - absorption_results: each index is a list of absorption information
            - structure: [(0) observed grams absorbed,
                          (1) clamped grams,
                          (2) total carbs in entry,
                          (3) remaining carbs,
                          (4) observed absorption start,
                          (5) observed absorption end,
                          (6) estimated time remaining]
        - absorption_timelines: 3 sublists, matched by index
            - structure: [(0) timeline start times,
                          (1) timeline end times,
                          (2) effect value during timeline interval (mg/dL)]
        - carb_entries: 5 sublists, matched by index
            - these lists are values that were calculated during map_ runtime
            - structure: [(0) carb sensitivities (mg/dL/G of carbohydrate),
                          (1) maximum carb absorption times (min),
                          (2) maximum absorption end times (datetime),
                          (3) last date effects were observed (datetime)
                          (4) total glucose effect expected for entry (mg/dL)]
    """
    assert len(carb_entry_starts) == len(carb_entry_quantities)\
        == len(carb_entry_absorptions), "expected input shapes to match"

    assert len(effect_starts) == len(effect_ends) == len(effect_values), \
        "expected input shapes to match"

    assert len(carb_ratio_starts) == len(carb_ratios),\
        "expected input shapes to match"

    assert len(sensitivity_starts) == len(sensitivity_ends)\
        == len(sensitivity_values), "expected input shapes to match"

    if (not carb_entry_starts
            or not carb_ratios
            or not sensitivity_starts):
        return ([], [], [])

    builder_entry_indexes = list(range(0, len(carb_entry_starts)))

    # CSF is in mg/dL/G
    builder_carb_sensitivities = [
        find_ratio_at_time(
            sensitivity_starts,
            sensitivity_ends,
            sensitivity_values,
            carb_entry_starts[i]
            ) /
        find_ratio_at_time(
            carb_ratio_starts,
            [],
            carb_ratios,
            carb_entry_starts[i]
            )
        for i in builder_entry_indexes
        ]

    # unit: G/s
    builder_max_absorb_times = [
        (carb_entry_absorptions[i]
         or default_absorption_time)
        * absorption_time_overrun
        for i in builder_entry_indexes
        ]

    builder_max_end_dates = [
        carb_entry_starts[i]
        + timedelta(minutes=builder_max_absorb_times[i] + delay)
        for i in builder_entry_indexes
        ]

    last_effect_dates = [
        effect_ends[len(effect_ends)-1]
        for i in builder_entry_indexes
        ]

    entry_effects = [
        carb_entry_quantities[i] * builder_carb_sensitivities[i]
        for i in builder_entry_indexes
        ]

    observed_effects = [0 for i in builder_entry_indexes]
    observed_completion_dates = [None for i in builder_entry_indexes]
    #   TODO: figure out how to represent without sublists
    observed_timeline_starts = [[] for i in builder_entry_indexes]
    observed_timeline_ends = [[] for i in builder_entry_indexes]
    observed_timeline_carb_values = [[] for i in builder_entry_indexes]

    assert len(builder_entry_indexes) == len(builder_carb_sensitivities)\
        == len(builder_max_absorb_times) == len(builder_max_end_dates)\
        == len(last_effect_dates), "expected shapes to match"

    def add_next_effect(entry_index, effect, start, end):
        if carb_entry_starts[entry_index] < start:
            return

        observed_effects[entry_index] += effect

        if not observed_completion_dates[entry_index]:
            # Continue recording the timeline until
            # 100% of the carbs have been observed
            observed_timeline_starts[entry_index].append(start)
            observed_timeline_ends[entry_index].append(end)
            observed_timeline_carb_values[entry_index].append(
                effect / builder_carb_sensitivities[entry_index]
            )

            # Once 100% of the carbs are observed, track the endDate
            # TODO: if having trouble debugging, try + Double(Float.ulpOfOne)
            if observed_effects[entry_index] >= entry_effects[entry_index]:
                observed_completion_dates[entry_index] = end

    for index in range(0, len(effect_starts)):

        if effect_starts[index] >= effect_ends[index]:
            continue

        # Select only the entries whose dates overlap the current date interval
        # These are not always contiguous, as maxEndDate varies between entries
        active_builders = []
        for j in builder_entry_indexes:
            if (effect_starts[index] < builder_max_end_dates[j]
                    and effect_starts[index] >= carb_entry_starts[j]):
                active_builders.append(j)

        # Ignore velocities < 0 when estimating carb absorption.
        # These are most likely the result of insulin absorption increases
        # such as during activity
        effect_value = max(0, effect_values[index])

        def reduce_func(previous, index_):
            return previous + (carb_entry_quantities[index_]
                               / builder_max_absorb_times[index_]
                               )
        # Sum the minimum absorption rates of each active entry to
        # determine how to split the active effects

        # ! had to implement my own reduce function bc
        # ! reduce wasn't working correctly for lists with one value
        previous = 0
        total_rate = 0
        for i in active_builders:
            rate_increase = reduce_func(previous, i)
            total_rate += rate_increase
            previous = rate_increase

        for b_index in active_builders:
            entry_effect = (carb_entry_quantities[b_index]
                            * builder_carb_sensitivities[b_index]
                           )
            remaining_effect = max(entry_effect, 0)
            # Apply a portion of the effect to this entry
            partial_effect_value = min(remaining_effect,
                                       (carb_entry_quantities[b_index]
                                        / builder_max_absorb_times[b_index]
                                        ) / total_rate * effect_value
                                       if total_rate != 0 and effect_value != 0
                                       else 0
                                       )
            total_rate -= (carb_entry_quantities[b_index]
                           / builder_max_absorb_times[b_index]
                           )
            effect_value -= partial_effect_value

            add_next_effect(
                b_index,
                partial_effect_value,
                effect_starts[index],
                effect_ends[index]
            )

            # If there's still remainder effects with no additional entries
            # to account them to, count them as overrun on the final entry
            if (effect_value > sys.float_info.epsilon
                    and b_index == (len(active_builders) - 1)
               ):
                add_next_effect(
                    b_index,
                    effect_value,
                    effect_starts[index],
                    effect_ends[index],
                    )

    def absorption_result(builder_index):
        # absorption list structure: [observed grams absorbed, clamped grams,
        # total carbs in entry, remaining carbs, observed absorption start,
        # observed absorption end, estimated time remaining]
        observed_grams = (observed_effects[builder_index]
                          / builder_carb_sensitivities[builder_index])

        entry_grams = carb_entry_quantities[builder_index]

        time = (time_interval_since(
            last_effect_dates[builder_index],
            carb_entry_starts[builder_index]
            ) / 60
                - delay
                )
        min_predicted_grams = linearly_absorbed_carbs(
            entry_grams,
            time,
            builder_max_absorb_times[builder_index]
        )
        clamped_grams = min(
            entry_grams,
            max(min_predicted_grams, observed_grams)
        )

        min_absorption_rate = (carb_entry_quantities[builder_index]
                               / builder_max_absorb_times[builder_index]
                               )
        estimated_time_remaining = ((entry_grams - clamped_grams)
                                    / min_absorption_rate
                                    if min_absorption_rate > 0
                                    else 0)
        absorption = [
            entry_grams,
            clamped_grams,
            entry_grams,
            entry_grams - clamped_grams,
            carb_entry_starts[builder_index],
            observed_completion_dates[builder_index]
            or last_effect_dates[builder_index],
            estimated_time_remaining
        ]

        return absorption

    # The timeline of observed absorption,
    # if greater than the minimum required absorption.
    def clamped_timeline(builder_index):
        entry_grams = carb_entry_quantities[builder_index]

        time = (time_interval_since(
            last_effect_dates[builder_index],
            carb_entry_starts[builder_index]
            ) / 60
                - delay
                )

        min_predicted_grams = linearly_absorbed_carbs(
            entry_grams,
            time,
            builder_max_absorb_times[builder_index]
        )
        return ([observed_timeline_starts[builder_index],
                 observed_timeline_ends[builder_index],
                 observed_timeline_carb_values[builder_index]
                 ] if (
                     observed_effects[builder_index]
                     / builder_carb_sensitivities[builder_index]
                     >= min_predicted_grams
                     )
                else None)

    def entry_properties(i):
        return [builder_carb_sensitivities[i],
                builder_max_absorb_times[i],
                builder_max_end_dates[i],
                last_effect_dates[i],
                entry_effects[i]
                ]

    entries = []
    absorptions = []
    timelines = []
    # TODO: possibily refactor without sublists
    for i in builder_entry_indexes:
        absorptions.append(absorption_result(i))
        timelines.append(clamped_timeline(i))
        entries.append(entry_properties(i))

    assert len(absorptions) == len(timelines) == len(entries),\
        "expect output shapes to match"

    return (absorptions, timelines, entries)


def linearly_absorbed_carbs(total, time, absorption_time):
    """
    Find absorbed carbs using a linear model

    Parameters:
    total -- total grams of carbs
    time -- relative time after eating (in minutes)
    absorption_time --  time for carbs to completely absorb (in minutes)

    Output:
    Grams of absorbed carbs
    """
    return total * linear_percent_absorption_at_time(time, absorption_time)


def linear_percent_absorption_at_time(time, absorption_time):
    """
    Find percent of absorbed carbs using a linear model

    Parameters:
    time -- relative time after eating (in minutes)
    absorption_time --  time for carbs to completely absorb (in minutes)

    Output:
    Percent of absorbed carbs
    """
    if time <= 0:
        return 0
    if time < absorption_time:
        return time / absorption_time
    return 1