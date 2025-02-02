from .constants import FEATURES, CHOICE_FIXATION_TIME
import numpy as np
import math
import pandas as pd
from itertools import repeat

def get_behavior_by_bins(bin_size, beh):
    """
    bin_size: in miliseconds, bin size
    data: dataframe for behavioral data from object features csv
    Returns: new dataframe with one-hot encoding of features, feedback
    """
    max_time = np.max(beh["TrialEnd"].values)
    max_bin_idx = math.ceil(max_time / bin_size)
    columns = FEATURES + ["CORRECT", "INCORRECT"]
    zipped = list(zip(columns, repeat("f4")))
    dtype = np.dtype(zipped)
    arr = np.zeros((max_bin_idx), dtype=dtype)

    for _, row in beh.iterrows():
        # grab features of item chosen
        item_chosen = int(row["ItemChosen"])
        color = row[f"Item{item_chosen}Color"]
        shape = row[f"Item{item_chosen}Shape"]
        pattern = row[f"Item{item_chosen}Pattern"]

        chosen_time = row["FeedbackOnset"] - CHOICE_FIXATION_TIME
        chosen_bin = math.floor(chosen_time / bin_size)
        arr[chosen_bin][color] = 1
        arr[chosen_bin][shape] = 1
        arr[chosen_bin][pattern] = 1

        feedback_bin = int(np.floor(row["FeedbackOnset"] / bin_size))
        # print(feedback_bin)
        if row["Response"] == "Correct":
            arr[feedback_bin]["CORRECT"] = 1
        elif row["Response"] == "Incorrect":
            arr[feedback_bin]["INCORRECT"] = 1
        else: 
            raise ValueError(f"{row['Response']} is undefined")
    df = pd.DataFrame(arr)
    df["bin_idx"] = np.arange(len(df))
    return df


def get_spikes_by_bins(bin_size, spike_times):
    """Given a bin_size and a series of spike times, return spike counts by bin. 
    Args:
        bin_size: size of bins in miliseconds
        spike_times: dataframe with unit_id, spike times. 
    Returns: 
        df with bin_idx, unit_* as columns, filled with spike counts
    """

    units = np.unique(spike_times.UnitID.values)
    num_time_bins = int(spike_times.SpikeTime.max() / bin_size) + 1
    bin_edges = np.arange(num_time_bins) * bin_size

    df = pd.DataFrame(data={'bin_idx': np.arange(num_time_bins)[:-1]})
    for unit in units:
        unit_spike_times = spike_times[spike_times.UnitID==unit].SpikeTime.values
        unit_spike_counts, _ = np.histogram(unit_spike_times, bins=bin_edges)
        df[f'unit_{unit}'] = unit_spike_counts
    return df

def get_trial_intervals(behavioral_data, event="FeedbackOnset", pre_interval=0, post_interval=0, bin_size=50):
    """Per trial, finds time interval surrounding some event in the behavioral data

    Args:
        behavioral_data: Dataframe describing each trial, must contain
            columns: TrialNumber, as well as the column corresponding to the  `event` parameter
        event: name of event to align around, must be present as a
            column name in behavioral_data Dataframe
        pre_interval: number of miliseconds before the event to include. Should be >= 0
        post_interval: number of miliseconds after the event to include. Should be >= 0

    Returns:
        DataFrame with num_trials length, columns: TrialNumber,
        IntervalStartTime, IntervalEndTime
    """
    if pre_interval >= 0 or post_interval >= 0:
        raise ValueError("Neither pre_interval: {pre_interval} or post_interval: {post_interval} should be negative")
    
    trial_event_times = behavioral_data[["TrialNumber", event]]

    intervals_df = pd.DataFrame(columns=["TrialNumber", "IntervalStartTime", "IntervalEndTime"])
    intervals_df["TrialNumber"] = trial_event_times["TrialNumber"].astype(int)
    intervals_df["IntervalStartTime"] = trial_event_times[event] - pre_interval
    intervals_df["IntervalEndTime"] = trial_event_times[event] + post_interval
    intervals_df["IntervalStartBin"] = np.floor(intervals_df["IntervalStartTime"] / bin_size).astype(int)
    intervals_df["IntervalEndBin"] = np.floor(intervals_df["IntervalEndTime"] / bin_size).astype(int)
    return intervals_df


def get_design_matrix(spikes_by_bins, beh_by_bins, columns, tau_pre, tau_post):
    """
    Reformats data as a design matrix dataframe, where for each of the specified columns, 
    additional columns are added for each of the time points between tau_pre and tau_post
    Args:
        spike_by_bins: df with bin_idx, unit_* as columns
        beh_by_bins: df with bin_idx, behavioral vars of interest as columns
        columns: columns to include, must be present in either spike_by_bins or beh_by_bins
        tau_pre: number of bins to look in the past
        tau_post: number of bins to look in the future
    Returns:
        df with bin_idx, columns for each time points between tau_pre and tau_post
        missing time shift values will be filled with nans
    """
    joint = pd.merge(spikes_by_bins, beh_by_bins, on="bin_idx", how="inner")
    res = pd.DataFrame()
    taus = np.arange(-tau_pre, tau_post)
    for tau in taus:
        shift_idx = -1 * tau
        column_names = [f"{x}_{tau}" for x in columns]
        res[column_names] = joint.shift(shift_idx)[columns]
    res["bin_idx"] = joint["bin_idx"]
    return res


def get_interval_bins(intervals):
    """
    Gets all the bins belonging to all the intervals
    Args:
        intervals: df with trialnumber, IntervalStartBin, IntervalEndBin
    Returns:
        np array of all bins for all trials falling between startbin and endbin
    """
    interval_bins = intervals.apply(lambda x: np.arange(x.IntervalStartBin, x.IntervalEndBin).astype(int), axis=1)
    return np.concatenate(interval_bins.to_numpy())