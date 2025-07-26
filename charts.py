import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
import seaborn as sns

def parse_info_logs(log_file="logs/info.log"):
   
    request_data = []
    network_data = []
    overall_summary = None
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                if '[agent]' in line:
                    json_part = line.split('[agent]', 1)[1].strip()
                    data = json.loads(json_part)
                    
                    if data.get('event_type') == 'request_processed':
                        request_data.append(data)
                    elif 'tool' in data and 'network_latency' in data:
                        network_data.append(data)
                    elif 'start' in data and 'end' in data and 'duration' in data:
                        overall_summary = data
                        
            except (json.JSONDecodeError, KeyError):
                continue
    
    return request_data, network_data, overall_summary

def parse_agent_logs(log_file="logs/agent.log"):
    agent_data = []
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                agent_data.append(data)
            except json.JSONDecodeError:
                continue
    
    return agent_data

def create_time_bins(start_time, end_time, bin_size_seconds=30):
    
    bins = []
    current = start_time
    while current < end_time:
        bins.append(current)
        current += timedelta(seconds=bin_size_seconds)
    bins.append(end_time)  # Add final bin edge
    return bins

def calculate_throughput_and_success(request_data, overall_start):
   
    if not request_data:
        return [], [], []
    
    for item in request_data:
        try:
            timestamp = datetime.fromisoformat(item['timestamp'])
            timestamps.append(timestamp)
        except (ValueError, KeyError):
            continue
        processed_counts.append(item['processed_count'])
        success_counts.append(item['success_count'])
    
    start_time = overall_start
    end_time = timestamps[-1] if timestamps else start_time + timedelta(seconds=30)
    bins = create_time_bins(start_time, end_time, 30)
    
    throughput_per_bin = []
    success_rate_per_bin = []
    bin_centers = []
    
    for i in range(len(bins) - 1):
        bin_start = bins[i]
        bin_end = bins[i + 1]
        bin_center = bin_start + (bin_end - bin_start) / 2
        
        requests_in_bin = [item for item in request_data 
                          if bin_start <= datetime.fromisoformat(item['timestamp']) <= bin_end]
        
        throughput = len(requests_in_bin) 
        
       
        if requests_in_bin:
            total_processed = sum(item['processed_count'] for item in requests_in_bin)
            total_successful = sum(item['success_count'] for item in requests_in_bin)
            success_rate = (total_successful / total_processed * 100) if total_processed > 0 else 0

        
        else:
            throughput = 0
            success_rate = 0
        
        throughput_per_bin.append(throughput)
        success_rate_per_bin.append(success_rate)
        bin_centers.append(bin_center)
    
    return bin_centers, throughput_per_bin, success_rate_per_bin

def create_throughput_chart(request_data, overall_summary, overall_start):
   
    bin_centers, throughput_per_bin, success_rate_per_bin = calculate_throughput_and_success(request_data, overall_start)
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    if bin_centers:
        ax.plot(bin_centers, throughput_per_bin, marker='o', linewidth=2, markersize=6, color='blue')
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Requests Processed (per 30s)', fontsize=12)
        ax.set_title('Throughput Over Time (30-second bins)', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax.xaxis.set_major_locator(mdates.SecondLocator(interval=30))
        plt.xticks(rotation=45)
    else:
        ax.text(0.5, 0.5, 'No throughput data available', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
    
    
    if overall_summary:
        config = overall_summary.get('configuration', {})
        summary_text = f"""Configuration:
Toxic Prob: {config.get('toxic_probability', 'N/A')}
Failure Prob: {config.get('failure_probability', 'N/A')}
Tool Limit: {config.get('tool_limit', 'N/A')}
Prompt Limit: {config.get('prompt_limit', 'N/A')}

Results:
Total Requests: {overall_summary.get('# of requests received', 'N/A')}
Processed: {overall_summary.get('# of requests processed', 'N/A')}
Successful: {overall_summary.get('# of successful requests', 'N/A')}
Duration: {overall_summary.get('duration', 0):.2f}s"""
        
        ax.text(0.02, 0.98, summary_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig('throughput_chart.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_success_rate_chart(request_data, overall_start):

    bin_centers, throughput_per_bin, success_rate_per_bin = calculate_throughput_and_success(request_data, overall_start)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    if bin_centers:
        ax.plot(bin_centers, success_rate_per_bin, marker='o', linewidth=2, markersize=6, color='green')
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Success Rate (%)', fontsize=12)
        ax.set_title('Success Rate Over Time (30-second bins)', fontsize=14, fontweight='bold')
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax.xaxis.set_major_locator(mdates.SecondLocator(interval=30))
        plt.xticks(rotation=45)
    else:
        ax.text(0.5, 0.5, 'No success rate data available', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
    
    plt.tight_layout()
    plt.savefig('success_rate_chart.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_network_latency_chart(network_data):
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    if network_data:
        timestamps = [datetime.fromisoformat(item['network_start']) for item in network_data]
        latencies = [item['network_latency'] for item in network_data]
        
        ax.plot(timestamps, latencies, marker='o', linewidth=2, markersize=6, color='orange')
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Network Latency (seconds)', fontsize=12)
        ax.set_title('Network Latency Over Time', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.xticks(rotation=45)
    else:
        ax.text(0.5, 0.5, 'No network latency data available', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
    
    plt.tight_layout()
    plt.savefig('network_latency_chart.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_tool_latency_chart(agent_data):
    fig, ax = plt.subplots(figsize=(12, 6))
    
    timestamps = []
    durations = []
    
    for item in agent_data:
        if 'start_time' in item and 'duration' in item and item['start_time']:
            try:
                timestamps.append(datetime.fromisoformat(item['start_time']))
                durations.append(item['duration'])
            except (ValueError, TypeError):
                continue
    
    if timestamps:
        ax.plot(timestamps, durations, marker='o', linewidth=2, markersize=6, color='red')
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Response Duration (seconds)', fontsize=12)
        ax.set_title('Agent Response Time Over Time', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.xticks(rotation=45)
    else:
        ax.text(0.5, 0.5, 'No tool latency data available', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
    
    plt.tight_layout()
    plt.savefig('tool_latency_chart.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_error_distribution_chart(agent_data):
   
    fig, ax = plt.subplots(figsize=(10, 6))
    
    error_counts = Counter()
    
    for item in agent_data:
        error_type = item.get('error_type', 'unknown')
        error_counts[error_type] += 1
    
   
    if len(error_counts) > 1 and 'none' in error_counts:
        del error_counts['none']
    
    if error_counts:
        labels = list(error_counts.keys())
        sizes = list(error_counts.values())
        colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#ff99cc', '#c2c2f0']
        
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', 
                                          colors=colors[:len(labels)], startangle=90)
        
        ax.set_title('Error Type Distribution', fontsize=14, fontweight='bold')
        
     
        for i, (label, count) in enumerate(error_counts.items()):
            texts[i].set_text(f'{label}\n({count})')
    else:
        ax.text(0.5, 0.5, 'No error data available', ha='center', va='center', 
                transform=ax.transAxes, fontsize=14)
        ax.set_title('Error Type Distribution', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('error_distribution_chart.png', dpi=300, bbox_inches='tight')
    plt.show()

def main():
   
   
    request_data, network_data, overall_summary = parse_info_logs()
    agent_data = parse_agent_logs()
    
    
    overall_start = None
    if overall_summary and 'start' in overall_summary:
        overall_start = datetime.fromisoformat(overall_summary['start'])
    elif request_data:
        overall_start = datetime.fromisoformat(request_data[0]['timestamp'])
    elif network_data:
        overall_start = datetime.fromisoformat(network_data[0]['network_start'])
    else:
        overall_start = datetime.now()
    
   
    create_throughput_chart(request_data, overall_summary, overall_start)
    create_success_rate_chart(request_data, overall_start)
    create_network_latency_chart(network_data)
    create_tool_latency_chart(agent_data)
    create_error_distribution_chart(agent_data)

if __name__ == "__main__":
    main()