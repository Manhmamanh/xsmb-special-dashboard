#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


ZIP_PATH = Path('/Users/Kuben/Downloads/vietnam-lottery-xsmb-analysis-main.zip')
CSV_NAME = 'vietnam-lottery-xsmb-analysis-main/data/xsmb.csv'
RAW_CSV_URL = 'https://raw.githubusercontent.com/khiemdoan/vietnam-lottery-xsmb-analysis/refs/heads/main/data/xsmb.csv'
OUT_PATH = Path(__file__).with_name('index.html')
WINDOW_DAYS = 100
SHORT_WINDOW_DAYS = 30


def format_display_date(value: str) -> str:
    return datetime.strptime(value, '%Y-%m-%d').strftime('%d-%m-%Y')


def parse_rows(raw: str) -> list[dict]:
    rows: list[dict] = []
    for item in csv.DictReader(io.StringIO(raw)):
        special = int(item['special'])
        rows.append(
            {
                'date': item['date'],
                'dateDisplay': format_display_date(item['date']),
                'special': special,
                'specialDisplay': f'{special:05d}',
                'tail': special % 100,
                'tailDisplay': f'{special % 100:02d}',
            }
        )
    return sorted(rows, key=lambda row: row['date'])


def read_rows() -> tuple[list[dict], str, str]:
    if ZIP_PATH.exists():
        with zipfile.ZipFile(ZIP_PATH) as archive:
            raw = archive.read(CSV_NAME).decode('utf-8')
        return parse_rows(raw), 'embedded', str(ZIP_PATH)

    with urllib.request.urlopen(RAW_CSV_URL, timeout=30) as response:
        raw = response.read().decode('utf-8')
    return parse_rows(raw), 'online-build', RAW_CSV_URL


def build_payload(rows: list[dict], source_mode: str, source_file: str) -> dict:
    latest = rows[-1]
    latest_date = datetime.strptime(latest['date'], '%Y-%m-%d')
    target_date = latest_date + timedelta(days=1)
    recent_rows = rows[-WINDOW_DAYS:]
    short_rows = rows[-SHORT_WINDOW_DAYS:]

    all_tails = [row['tail'] for row in rows]
    recent_tails = [row['tail'] for row in recent_rows]
    short_tails = [row['tail'] for row in short_rows]
    count_all = Counter(all_tails)
    count_recent = Counter(recent_tails)
    count_short = Counter(short_tails)

    stats = []
    total_history = len(rows)
    for number in range(100):
        gap = None
        last_date = None
        for index in range(len(rows) - 1, -1, -1):
            if rows[index]['tail'] == number:
                gap = len(rows) - 1 - index
                last_date = rows[index]['date']
                break

        # Enhanced prediction algorithm with 5 factors:
        # 30% uniform prior (baseline)
        # 30% short-term 30-day frequency (hot numbers)
        # 20% medium-term 100-day frequency
        # 10% long-term history
        # 10% gap factor (rewards numbers overdue up to 30 days)
        p_uniform = 0.01
        p_short = (count_short[number] + 1) / (SHORT_WINDOW_DAYS + 100)
        p_recent = (count_recent[number] + 1) / (WINDOW_DAYS + 100)
        p_long = (count_all[number] + 1) / (total_history + 100)
        
        gap_factor = min(gap, 30) / 30.0 if gap is not None else 0.0
        p_gap = p_uniform * (1 + 0.5 * gap_factor)
        
        probability = 0.30 * p_uniform + 0.30 * p_short + 0.20 * p_recent + 0.10 * p_long + 0.10 * p_gap

        stats.append(
            {
                'number': f'{number:02d}',
                'value': number,
                'count100': count_recent[number],
                'count30': count_short[number],
                'countAll': count_all[number],
                'gap': gap,
                'lastSeen': last_date,
                'lastSeenDisplay': format_display_date(last_date) if last_date else '-',
                'recentRate': count_recent[number] / WINDOW_DAYS,
                'historyRate': count_all[number] / total_history,
                'probability': probability,
            }
        )

    total_probability = sum(item['probability'] for item in stats)
    for item in stats:
        item['probability'] = item['probability'] / total_probability

    ranked = sorted(
        stats,
        key=lambda item: (
            item['probability'],
            item['count100'],
            item['count30'],
            item['countAll'],
            -item['gap'],
        ),
        reverse=True,
    )
    for rank, item in enumerate(ranked, start=1):
        item['rank'] = rank
    by_number = {item['number']: item for item in ranked}
    stats = [by_number[f'{number:02d}'] for number in range(100)]

    most_common_count = max(item['count100'] for item in stats)
    most_common_numbers = [item['number'] for item in stats if item['count100'] == most_common_count]
    missing_numbers = [item['number'] for item in stats if item['count100'] == 0]

    return {
        'metadata': {
            'sourceFile': source_file,
            'sourceUrl': RAW_CSV_URL,
            'sourceMode': source_mode,
            'historyRows': total_history,
            'windowDays': WINDOW_DAYS,
            'shortWindowDays': SHORT_WINDOW_DAYS,
            'startDate': recent_rows[0]['date'],
            'endDate': latest['date'],
            'startDateDisplay': format_display_date(recent_rows[0]['date']),
            'endDateDisplay': latest['dateDisplay'],
            'targetDate': target_date.strftime('%Y-%m-%d'),
            'targetDateDisplay': target_date.strftime('%d-%m-%Y'),
            'uniqueCount': len(set(recent_tails)),
            'missingCount': len(missing_numbers),
            'missingNumbers': missing_numbers,
            'mostCommonCount': most_common_count,
            'mostCommonNumbers': most_common_numbers,
            'latestTail': latest['tailDisplay'],
            'latestSpecial': latest['specialDisplay'],
        },
        'last100': recent_rows,
        'numberStats': stats,
        'top10': ranked[:10],
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>XSMB - Thống kê 2 số cuối giải đặc biệt</title>
  <style>
    :root {
      --bg: #f5f7f9;
      --surface: #ffffff;
      --surface-soft: #eef3f6;
      --ink: #17202a;
      --muted: #5d6570;
      --line: #d9e0e7;
      --header: #20262e;
      --teal: #087f8c;
      --blue: #2f5d99;
      --green: #2f7d58;
      --gold: #b57418;
      --red: #b6424b;
      --violet: #6b5ca5;
      --radius: 8px;
      --shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      line-height: 1.5;
    }

    button,
    input {
      font: inherit;
    }

    .app {
      max-width: 1440px;
      margin: 0 auto;
      padding: 16px;
    }

    .topbar {
      align-items: flex-start;
      background: var(--header);
      border-radius: var(--radius);
      color: #fff;
      display: flex;
      gap: 18px;
      justify-content: space-between;
      margin-bottom: 16px;
      padding: 22px 24px;
    }

    .title-block {
      max-width: 820px;
    }

    h1 {
      font-size: 24px;
      line-height: 1.2;
      margin: 0 0 8px;
      font-weight: 700;
    }

    .subtitle {
      color: rgba(255, 255, 255, 0.74);
      margin: 0;
      font-size: 14px;
    }

    .asof {
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: var(--radius);
      min-width: 250px;
      padding: 12px 14px;
      text-align: right;
    }

    .asof span {
      color: rgba(255, 255, 255, 0.7);
      display: block;
      font-size: 12px;
      margin-bottom: 4px;
    }

    .asof strong {
      font-size: 18px;
    }

    .status-row {
      align-items: center;
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      margin-top: 10px;
    }

    .data-status {
      color: rgba(255, 255, 255, 0.72);
      font-size: 11px;
      line-height: 1.25;
    }

    .refresh-button {
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.22);
      border-radius: 6px;
      color: #fff;
      cursor: pointer;
      font-size: 12px;
      min-height: 30px;
      padding: 5px 9px;
      white-space: nowrap;
    }

    .refresh-button:hover {
      background: rgba(255, 255, 255, 0.2);
    }

    .kpi-grid {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(5, minmax(160px, 1fr));
      margin-bottom: 16px;
    }

    .kpi {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 16px;
    }

    .kpi-label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }

    .kpi-value {
      font-size: 26px;
      font-weight: 750;
      line-height: 1.15;
    }

    .kpi-note {
      color: var(--muted);
      font-size: 12px;
      margin-top: 7px;
    }

    .section-title {
      align-items: baseline;
      display: flex;
      gap: 10px;
      justify-content: space-between;
      margin: 20px 0 10px;
    }

    .section-title h2 {
      font-size: 18px;
      margin: 0;
    }

    .section-title p {
      color: var(--muted);
      font-size: 13px;
      margin: 0;
    }

    .candidate-grid {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(10, minmax(96px, 1fr));
      margin-bottom: 16px;
    }

    .candidate {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      min-height: 132px;
      padding: 13px;
      position: relative;
    }

    .candidate::before {
      background: var(--teal);
      border-radius: 4px;
      content: "";
      height: 4px;
      left: 12px;
      position: absolute;
      right: 12px;
      top: 0;
    }

    .candidate:nth-child(2n)::before { background: var(--blue); }
    .candidate:nth-child(3n)::before { background: var(--gold); }
    .candidate:nth-child(4n)::before { background: var(--green); }
    .candidate:nth-child(5n)::before { background: var(--red); }

    .rank {
      color: var(--muted);
      font-size: 12px;
    }

    .candidate-number {
      font-size: 30px;
      font-weight: 800;
      margin: 6px 0 2px;
    }

    .probability {
      color: var(--teal);
      font-size: 18px;
      font-weight: 750;
    }

    .candidate-meta {
      color: var(--muted);
      font-size: 12px;
      margin-top: 7px;
    }

    .panel-grid {
      display: grid;
      gap: 16px;
      grid-template-columns: 1.1fr 0.9fr;
      margin-bottom: 16px;
    }

    .panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 18px;
    }

    .panel-header {
      align-items: center;
      display: flex;
      gap: 12px;
      justify-content: space-between;
      margin-bottom: 14px;
    }

    .panel-header h3 {
      font-size: 15px;
      margin: 0;
    }

    .segmented {
      background: var(--surface-soft);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      display: inline-flex;
      gap: 3px;
      padding: 3px;
    }

    .segmented button {
      background: transparent;
      border: 0;
      border-radius: 6px;
      color: var(--muted);
      cursor: pointer;
      font-size: 12px;
      min-height: 30px;
      padding: 5px 9px;
    }

    .segmented button.active {
      background: var(--surface);
      color: var(--ink);
      box-shadow: var(--shadow);
      font-weight: 650;
    }

    .heatmap-wrap {
      overflow-x: auto;
    }

    .heatmap {
      display: grid;
      gap: 6px;
      grid-template-columns: repeat(10, minmax(54px, 1fr));
      min-width: 620px;
    }

    .heat-cell {
      aspect-ratio: 1.1;
      border: 1px solid rgba(23, 32, 42, 0.1);
      border-radius: 7px;
      color: var(--ink);
      cursor: pointer;
      display: grid;
      min-height: 54px;
      padding: 6px;
      place-items: center;
      text-align: center;
    }

    .heat-cell strong {
      display: block;
      font-size: 15px;
      line-height: 1.1;
    }

    .heat-cell span {
      color: rgba(23, 32, 42, 0.74);
      display: block;
      font-size: 11px;
      line-height: 1.1;
      margin-top: 3px;
    }

    .heat-cell.selected {
      outline: 3px solid rgba(8, 127, 140, 0.45);
      outline-offset: 1px;
    }

    .heat-cell.top10 {
      border-color: rgba(181, 116, 24, 0.7);
    }

    .bar-list {
      display: grid;
      gap: 8px;
    }

    .bar-row {
      align-items: center;
      display: grid;
      gap: 9px;
      grid-template-columns: 42px 1fr 56px;
    }

    .bar-label {
      font-weight: 750;
    }

    .bar-track {
      background: var(--surface-soft);
      border-radius: 999px;
      height: 16px;
      overflow: hidden;
    }

    .bar-fill {
      background: var(--blue);
      border-radius: 999px;
      height: 100%;
      min-width: 3px;
    }

    .bar-value {
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    .selected-detail {
      background: var(--surface-soft);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(4, 1fr);
      margin-top: 16px;
      padding: 12px;
    }

    .detail-number {
      align-items: center;
      display: flex;
      gap: 10px;
    }

    .detail-number strong {
      font-size: 34px;
      line-height: 1;
    }

    .detail-cell span {
      color: var(--muted);
      display: block;
      font-size: 11px;
      margin-bottom: 3px;
    }

    .detail-cell b {
      font-size: 15px;
    }

    .timeline {
      display: grid;
      gap: 6px;
      grid-template-columns: repeat(25, 1fr);
    }

    .draw-dot {
      align-items: center;
      background: var(--surface-soft);
      border: 1px solid var(--line);
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      justify-content: center;
      min-height: 44px;
      padding: 4px;
    }

    .draw-dot b {
      font-size: 13px;
      line-height: 1.1;
    }

    .draw-dot span {
      color: var(--muted);
      font-size: 9px;
      line-height: 1.1;
      margin-top: 2px;
    }

    .draw-dot.top10 {
      background: rgba(181, 116, 24, 0.12);
      border-color: rgba(181, 116, 24, 0.45);
    }

    .draw-dot.selected {
      background: rgba(8, 127, 140, 0.12);
      border-color: rgba(8, 127, 140, 0.58);
    }

    .method {
      background: #fff9ed;
      border: 1px solid #ead7b8;
      border-radius: var(--radius);
      color: #49361c;
      font-size: 13px;
      margin-bottom: 16px;
      padding: 14px 16px;
    }

    .method strong {
      color: #2b2218;
    }

    .table-toolbar {
      align-items: center;
      display: flex;
      gap: 10px;
      justify-content: space-between;
      margin-bottom: 12px;
    }

    .search {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      min-height: 36px;
      padding: 7px 10px;
      width: 190px;
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      border-collapse: collapse;
      font-size: 13px;
      min-width: 920px;
      width: 100%;
    }

    th,
    td {
      border-bottom: 1px solid #edf0f3;
      padding: 9px 10px;
      text-align: left;
      white-space: nowrap;
    }

    th {
      color: var(--muted);
      cursor: pointer;
      font-size: 12px;
      font-weight: 700;
      user-select: none;
    }

    tbody tr:hover {
      background: #f8fafb;
    }

    .num-pill {
      background: var(--surface-soft);
      border: 1px solid var(--line);
      border-radius: 999px;
      display: inline-block;
      font-weight: 750;
      min-width: 42px;
      padding: 3px 8px;
      text-align: center;
    }

    .rank-pill {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }

    .footer {
      color: var(--muted);
      font-size: 12px;
      margin: 18px 0 4px;
      text-align: center;
    }

    @media (max-width: 1180px) {
      .kpi-grid {
        grid-template-columns: repeat(3, 1fr);
      }

      .candidate-grid {
        grid-template-columns: repeat(5, 1fr);
      }

      .panel-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 760px) {
      .app {
        padding: 10px;
      }

      .topbar,
      .table-toolbar,
      .panel-header,
      .section-title {
        align-items: flex-start;
        flex-direction: column;
      }

      .asof {
        min-width: 0;
        text-align: left;
        width: 100%;
      }

      .kpi-grid {
        grid-template-columns: repeat(2, 1fr);
      }

      .candidate-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .selected-detail {
        grid-template-columns: repeat(2, 1fr);
      }

      .timeline {
        grid-template-columns: repeat(10, 1fr);
      }
    }

    @media print {
      body {
        background: #fff;
      }

      .segmented,
      .search {
        display: none;
      }

      .panel,
      .kpi,
      .candidate {
        box-shadow: none;
      }
    }
  </style>
</head>
<body>
  <main class="app">
    <header class="topbar">
      <div class="title-block">
        <h1>Thống kê 2 số cuối giải đặc biệt XSMB</h1>
        <p class="subtitle" id="subtitle"></p>
      </div>
      <div class="asof">
        <span>Dự báo tham khảo cho ngày</span>
        <strong id="targetDate"></strong>
        <div class="status-row">
          <span class="data-status" id="dataStatus">Đang chuẩn bị dữ liệu...</span>
          <button class="refresh-button" id="refreshButton" type="button">Làm mới</button>
        </div>
      </div>
    </header>

    <section class="kpi-grid" id="kpis"></section>

    <div class="section-title">
      <h2>10 số ưu tiên theo mô hình</h2>
      <p>Xác suất đã co về mốc lý thuyết 1% để tránh phóng đại từ mẫu 100 ngày.</p>
    </div>
    <section class="candidate-grid" id="candidateGrid"></section>

    <div class="method">
      <strong>Lưu ý thống kê:</strong> thuật toán dự đoán đã được tối ưu hóa dựa trên 5 trọng số: 30% xác suất cơ bản (đều), 30% xu hướng ngắn hạn (30 ngày gần nhất), 20% xu hướng trung hạn (100 ngày), 10% tần suất lịch sử, và 10% điểm lô gan (chu kỳ chưa về, tối đa 30 ngày). Bảng này giúp bắt xu hướng tốt hơn nhưng không có gì là chắc chắn tuyệt đối.
    </div>

    <section class="panel-grid">
      <div class="panel">
        <div class="panel-header">
          <h3>Bản đồ 00-99</h3>
          <div class="segmented" aria-label="Chỉ số bản đồ">
            <button class="active" data-metric="count100">100 ngày</button>
            <button data-metric="probability">Xác suất</button>
            <button data-metric="gap">Khoảng cách</button>
          </div>
        </div>
        <div class="heatmap-wrap">
          <div class="heatmap" id="heatmap"></div>
        </div>
        <div class="selected-detail" id="selectedDetail"></div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <h3>Tần suất cao nhất trong 100 ngày</h3>
        </div>
        <div class="bar-list" id="frequencyBars"></div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h3>Dòng thời gian 100 kỳ gần nhất</h3>
      </div>
      <div class="timeline" id="timeline"></div>
    </section>

    <section class="panel" style="margin-top: 16px;">
      <div class="table-toolbar">
        <div>
          <h3 style="font-size: 15px; margin: 0;">Bảng đầy đủ 100 số</h3>
          <p style="color: var(--muted); font-size: 12px; margin: 4px 0 0;">Nhấn tiêu đề cột để sắp xếp.</p>
        </div>
        <input class="search" id="numberSearch" inputmode="numeric" placeholder="Lọc số, ví dụ 54">
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th data-sort="rank">Hạng</th>
              <th data-sort="number">Số</th>
              <th data-sort="probability">Xác suất mô hình</th>
              <th data-sort="count100">Số lần / 100 ngày</th>
              <th data-sort="recentRate">Tỷ lệ 100 ngày</th>
              <th data-sort="count30">Số lần / 30 ngày</th>
              <th data-sort="gap">Khoảng cách</th>
              <th data-sort="countAll">Số lần toàn lịch sử</th>
              <th data-sort="lastSeen">Lần gần nhất</th>
            </tr>
          </thead>
          <tbody id="numbersTable"></tbody>
        </table>
      </div>
    </section>

    <section class="panel" style="margin-top: 16px;">
      <div class="panel-header">
        <h3>100 kết quả giải đặc biệt gần nhất</h3>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ngày</th>
              <th>Giải đặc biệt</th>
              <th>2 số cuối</th>
              <th>Tần suất số này / 100 ngày</th>
              <th>Xác suất mô hình</th>
            </tr>
          </thead>
          <tbody id="drawTable"></tbody>
        </table>
      </div>
    </section>

    <div class="footer" id="footer"></div>
  </main>

  <script>
    const EMBEDDED_APP_DATA = __APP_DATA__;
    const RAW_CSV_URL = '__RAW_CSV_URL__';
    const WINDOW_DAYS = 100;
    const SHORT_WINDOW_DAYS = 30;

    let APP_DATA = EMBEDDED_APP_DATA;
    let statsByNumber = new Map();
    let top10Set = new Set();

    const state = {
      metric: 'count100',
      sortField: 'rank',
      sortDir: 'asc',
      selected: APP_DATA.top10[0].number,
    };

    function reindexData() {
      statsByNumber = new Map(APP_DATA.numberStats.map((item) => [item.number, item]));
      top10Set = new Set(APP_DATA.top10.map((item) => item.number));
      if (!statsByNumber.has(state.selected)) {
        state.selected = APP_DATA.top10[0].number;
      }
    }

    function pct(value, digits = 2) {
      return `${(value * 100).toFixed(digits)}%`;
    }

    function numberList(values, limit = 8) {
      if (values.length <= limit) return values.join(', ');
      return `${values.slice(0, limit).join(', ')} +${values.length - limit}`;
    }

    function setText(id, value) {
      document.getElementById(id).textContent = value;
    }

    function setStatus(message) {
      const status = document.getElementById('dataStatus');
      if (status) status.textContent = message;
    }

    function pad2(value) {
      return String(value).padStart(2, '0');
    }

    function parseIsoDate(value) {
      const [year, month, day] = value.split('-').map(Number);
      return new Date(year, month - 1, day);
    }

    function dateToIso(date) {
      return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
    }

    function addDays(value, days) {
      const date = parseIsoDate(value);
      date.setDate(date.getDate() + days);
      return dateToIso(date);
    }

    function formatDisplayDate(value) {
      if (!value) return '-';
      const [year, month, day] = value.split('-');
      return `${day}-${month}-${year}`;
    }

    function csvToRows(text) {
      const lines = text.trim().split(/\r?\n/).filter(Boolean);
      const headers = lines.shift().split(',');
      const dateIndex = headers.indexOf('date');
      const specialIndex = headers.indexOf('special');
      if (dateIndex < 0 || specialIndex < 0) {
        throw new Error('CSV không có cột date/special');
      }

      return lines.map((line) => {
        const columns = line.split(',');
        const special = Number(columns[specialIndex]);
        const tail = special % 100;
        const date = columns[dateIndex];
        return {
          date,
          dateDisplay: formatDisplayDate(date),
          special,
          specialDisplay: String(special).padStart(5, '0'),
          tail,
          tailDisplay: pad2(tail),
        };
      }).sort((a, b) => a.date.localeCompare(b.date));
    }

    function buildPayloadFromRows(rows, sourceMode) {
      const latest = rows[rows.length - 1];
      const recentRows = rows.slice(-WINDOW_DAYS);
      const shortRows = rows.slice(-SHORT_WINDOW_DAYS);
      const countAll = Array(100).fill(0);
      const countRecent = Array(100).fill(0);
      const countShort = Array(100).fill(0);

      rows.forEach((row) => countAll[row.tail] += 1);
      recentRows.forEach((row) => countRecent[row.tail] += 1);
      shortRows.forEach((row) => countShort[row.tail] += 1);

      const stats = [];
      for (let number = 0; number < 100; number += 1) {
        let gap = null;
        let lastSeen = null;
        for (let index = rows.length - 1; index >= 0; index -= 1) {
          if (rows[index].tail === number) {
            gap = rows.length - 1 - index;
            lastSeen = rows[index].date;
            break;
          }
        }

        const pUniform = 0.01;
        const pRecent = (countRecent[number] + 1) / (WINDOW_DAYS + 100);
        const pLong = (countAll[number] + 1) / (rows.length + 100);
        const probability = 0.60 * pUniform + 0.25 * pRecent + 0.15 * pLong;

        stats.push({
          number: pad2(number),
          value: number,
          count100: countRecent[number],
          count30: countShort[number],
          countAll: countAll[number],
          gap,
          lastSeen,
          lastSeenDisplay: formatDisplayDate(lastSeen),
          recentRate: countRecent[number] / WINDOW_DAYS,
          historyRate: countAll[number] / rows.length,
          probability,
        });
      }

      const totalProbability = stats.reduce((sum, item) => sum + item.probability, 0);
      stats.forEach((item) => {
        item.probability = item.probability / totalProbability;
      });

      const ranked = [...stats].sort((a, b) => {
        return (
          b.probability - a.probability ||
          b.count100 - a.count100 ||
          b.count30 - a.count30 ||
          b.countAll - a.countAll ||
          (a.gap ?? 999999) - (b.gap ?? 999999)
        );
      });
      ranked.forEach((item, index) => {
        item.rank = index + 1;
      });

      const byNumber = new Map(ranked.map((item) => [item.number, item]));
      const orderedStats = Array.from({ length: 100 }, (_, number) => byNumber.get(pad2(number)));
      const mostCommonCount = Math.max(...orderedStats.map((item) => item.count100));
      const mostCommonNumbers = orderedStats.filter((item) => item.count100 === mostCommonCount).map((item) => item.number);
      const missingNumbers = orderedStats.filter((item) => item.count100 === 0).map((item) => item.number);
      const targetDate = addDays(latest.date, 1);

      return {
        metadata: {
          sourceFile: sourceMode === 'online' ? RAW_CSV_URL : EMBEDDED_APP_DATA.metadata.sourceFile,
          sourceUrl: RAW_CSV_URL,
          sourceMode,
          historyRows: rows.length,
          windowDays: WINDOW_DAYS,
          shortWindowDays: SHORT_WINDOW_DAYS,
          startDate: recentRows[0].date,
          endDate: latest.date,
          startDateDisplay: recentRows[0].dateDisplay,
          endDateDisplay: latest.dateDisplay,
          targetDate,
          targetDateDisplay: formatDisplayDate(targetDate),
          uniqueCount: new Set(recentRows.map((row) => row.tail)).size,
          missingCount: missingNumbers.length,
          missingNumbers,
          mostCommonCount,
          mostCommonNumbers,
          latestTail: latest.tailDisplay,
          latestSpecial: latest.specialDisplay,
        },
        last100: recentRows,
        numberStats: orderedStats,
        top10: ranked.slice(0, 10),
      };
    }

    function renderHeader() {
      const meta = APP_DATA.metadata;
      setText('subtitle', `Nguồn dữ liệu: ${meta.startDateDisplay} đến ${meta.endDateDisplay}. Kết quả mới nhất: ${meta.latestSpecial}, đuôi ${meta.latestTail}.`);
      setText('targetDate', meta.targetDateDisplay);
      const sourceLabel = meta.sourceMode === 'online'
        ? 'GitHub raw CSV mới nhất'
        : meta.sourceMode === 'online-build'
          ? 'GitHub raw CSV tại thời điểm build'
          : 'dữ liệu nhúng dự phòng';
      setText('footer', `Dữ liệu đọc từ ${sourceLabel}. Tổng lịch sử: ${meta.historyRows.toLocaleString('vi-VN')} kỳ. Nguồn: ${meta.sourceUrl || meta.sourceFile}.`);
    }

    function renderKPIs() {
      const meta = APP_DATA.metadata;
      const kpis = [
        ['Số kỳ phân tích', meta.windowDays, `${meta.startDateDisplay} - ${meta.endDateDisplay}`],
        ['Số khác nhau', `${meta.uniqueCount}/100`, `${meta.missingCount} số chưa xuất hiện`],
        ['Xuất hiện nhiều nhất', numberList(meta.mostCommonNumbers), `${meta.mostCommonCount} lần trong 100 ngày`],
        ['Đuôi mới nhất', meta.latestTail, `Giải đặc biệt ${meta.latestSpecial}`],
        ['Mốc lý thuyết', '1.00%', 'Cho mỗi số 00-99'],
      ];
      document.getElementById('kpis').innerHTML = kpis.map(([label, value, note]) => `
        <article class="kpi">
          <div class="kpi-label">${label}</div>
          <div class="kpi-value">${value}</div>
          <div class="kpi-note">${note}</div>
        </article>
      `).join('');
    }

    function renderCandidates() {
      document.getElementById('candidateGrid').innerHTML = APP_DATA.top10.map((item, index) => `
        <article class="candidate" data-number="${item.number}">
          <div class="rank">#${index + 1}</div>
          <div class="candidate-number">${item.number}</div>
          <div class="probability">${pct(item.probability)}</div>
          <div class="candidate-meta">${item.count100} lần / 100 ngày<br>${item.count30} lần / 30 ngày<br>Cách ${item.gap} kỳ</div>
        </article>
      `).join('');
      document.querySelectorAll('.candidate').forEach((item) => {
        item.addEventListener('click', () => {
          state.selected = item.dataset.number;
          renderAll();
        });
      });
    }

    function metricValue(item) {
      if (state.metric === 'probability') return item.probability;
      if (state.metric === 'gap') return item.gap;
      return item.count100;
    }

    function metricLabel(item) {
      if (state.metric === 'probability') return pct(item.probability);
      if (state.metric === 'gap') return `${item.gap} kỳ`;
      return `${item.count100} lần`;
    }

    function heatColor(item, maxValue) {
      const value = metricValue(item);
      const ratio = maxValue ? value / maxValue : 0;
      const alpha = 0.08 + Math.min(0.72, ratio * 0.72);
      if (state.metric === 'probability') return `rgba(47, 125, 88, ${alpha})`;
      if (state.metric === 'gap') return `rgba(181, 116, 24, ${alpha})`;
      return `rgba(47, 93, 153, ${alpha})`;
    }

    function renderHeatmap() {
      const maxValue = Math.max(...APP_DATA.numberStats.map(metricValue));
      const html = APP_DATA.numberStats.map((item) => {
        const classes = [
          'heat-cell',
          item.number === state.selected ? 'selected' : '',
          top10Set.has(item.number) ? 'top10' : '',
        ].filter(Boolean).join(' ');
        return `
          <button class="${classes}" data-number="${item.number}" style="background:${heatColor(item, maxValue)}">
            <strong>${item.number}</strong>
            <span>${metricLabel(item)}</span>
          </button>
        `;
      }).join('');
      document.getElementById('heatmap').innerHTML = html;
      document.querySelectorAll('.heat-cell').forEach((cell) => {
        cell.addEventListener('click', () => {
          state.selected = cell.dataset.number;
          renderAll();
        });
      });
    }

    function renderSelectedDetail() {
      const item = statsByNumber.get(state.selected);
      document.getElementById('selectedDetail').innerHTML = `
        <div class="detail-number">
          <strong>${item.number}</strong>
          <span class="rank-pill">Hạng #${item.rank}</span>
        </div>
        <div class="detail-cell"><span>Xác suất mô hình</span><b>${pct(item.probability)}</b></div>
        <div class="detail-cell"><span>100 ngày</span><b>${item.count100} lần (${pct(item.recentRate)})</b></div>
        <div class="detail-cell"><span>Lần gần nhất</span><b>${item.lastSeenDisplay}</b></div>
      `;
    }

    function renderFrequencyBars() {
      const rows = [...APP_DATA.numberStats]
        .sort((a, b) => b.count100 - a.count100 || b.probability - a.probability)
        .slice(0, 20);
      const maxCount = Math.max(...rows.map((item) => item.count100));
      document.getElementById('frequencyBars').innerHTML = rows.map((item, index) => {
        const width = maxCount ? (item.count100 / maxCount) * 100 : 0;
        const color = index % 5 === 0 ? 'var(--teal)' : index % 5 === 1 ? 'var(--blue)' : index % 5 === 2 ? 'var(--gold)' : index % 5 === 3 ? 'var(--green)' : 'var(--red)';
        return `
          <div class="bar-row">
            <div class="bar-label">${item.number}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${width}%; background:${color};"></div></div>
            <div class="bar-value">${item.count100} lần</div>
          </div>
        `;
      }).join('');
    }

    function renderTimeline() {
      document.getElementById('timeline').innerHTML = APP_DATA.last100.map((row) => {
        const classes = [
          'draw-dot',
          row.tailDisplay === state.selected ? 'selected' : '',
          top10Set.has(row.tailDisplay) ? 'top10' : '',
        ].filter(Boolean).join(' ');
        return `
          <button class="${classes}" data-number="${row.tailDisplay}" title="${row.dateDisplay} - ${row.specialDisplay}">
            <b>${row.tailDisplay}</b>
            <span>${row.dateDisplay.slice(0, 5)}</span>
          </button>
        `;
      }).join('');
      document.querySelectorAll('.draw-dot').forEach((dot) => {
        dot.addEventListener('click', () => {
          state.selected = dot.dataset.number;
          renderAll();
        });
      });
    }

    function compareValues(a, b, field) {
      const av = a[field];
      const bv = b[field];
      if (typeof av === 'number' && typeof bv === 'number') return av - bv;
      return String(av).localeCompare(String(bv), 'vi');
    }

    function renderNumbersTable() {
      const query = document.getElementById('numberSearch').value.trim();
      const rows = APP_DATA.numberStats
        .filter((item) => !query || item.number.includes(query.padStart(Math.min(query.length, 2), '0')) || item.number.includes(query))
        .sort((a, b) => {
          const result = compareValues(a, b, state.sortField);
          return state.sortDir === 'asc' ? result : -result;
        });
      document.getElementById('numbersTable').innerHTML = rows.map((item) => `
        <tr>
          <td><span class="rank-pill">#${item.rank}</span></td>
          <td><span class="num-pill">${item.number}</span></td>
          <td>${pct(item.probability)}</td>
          <td>${item.count100}</td>
          <td>${pct(item.recentRate)}</td>
          <td>${item.count30}</td>
          <td>${item.gap} kỳ</td>
          <td>${item.countAll}</td>
          <td>${item.lastSeenDisplay}</td>
        </tr>
      `).join('');
    }

    function renderDrawTable() {
      document.getElementById('drawTable').innerHTML = [...APP_DATA.last100].reverse().map((row) => {
        const item = statsByNumber.get(row.tailDisplay);
        return `
          <tr>
            <td>${row.dateDisplay}</td>
            <td>${row.specialDisplay}</td>
            <td><span class="num-pill">${row.tailDisplay}</span></td>
            <td>${item.count100} lần</td>
            <td>${pct(item.probability)}</td>
          </tr>
        `;
      }).join('');
    }

    function renderAll() {
      renderHeatmap();
      renderSelectedDetail();
      renderTimeline();
      renderNumbersTable();
    }

    function renderDashboard() {
      reindexData();
      renderHeader();
      renderKPIs();
      renderCandidates();
      renderFrequencyBars();
      renderDrawTable();
      renderAll();
    }

    async function loadLatestData() {
      const refreshButton = document.getElementById('refreshButton');
      try {
        if (refreshButton) refreshButton.disabled = true;
        setStatus('Đang tải dữ liệu mới nhất...');
        const response = await fetch(`${RAW_CSV_URL}?v=${Date.now()}`, { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(`GitHub trả về HTTP ${response.status}`);
        }
        const csvText = await response.text();
        const rows = csvToRows(csvText);
        if (rows.length < WINDOW_DAYS) {
          throw new Error('CSV không đủ dữ liệu để thống kê 100 ngày');
        }
        APP_DATA = buildPayloadFromRows(rows, 'online');
        state.selected = APP_DATA.top10[0].number;
        renderDashboard();
        setStatus(`Đã cập nhật từ GitHub: ${APP_DATA.metadata.endDateDisplay}`);
      } catch (error) {
        APP_DATA = EMBEDDED_APP_DATA;
        state.selected = APP_DATA.top10[0].number;
        renderDashboard();
        setStatus(`Không tải được GitHub, đang dùng dữ liệu dự phòng: ${error.message}`);
      } finally {
        if (refreshButton) refreshButton.disabled = false;
      }
    }

    document.querySelectorAll('[data-metric]').forEach((button) => {
      button.addEventListener('click', () => {
        document.querySelectorAll('[data-metric]').forEach((item) => item.classList.remove('active'));
        button.classList.add('active');
        state.metric = button.dataset.metric;
        renderAll();
      });
    });

    document.querySelectorAll('th[data-sort]').forEach((header) => {
      header.addEventListener('click', () => {
        const field = header.dataset.sort;
        if (state.sortField === field) {
          state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
        } else {
          state.sortField = field;
          state.sortDir = field === 'rank' || field === 'number' ? 'asc' : 'desc';
        }
        renderNumbersTable();
      });
    });

    document.getElementById('numberSearch').addEventListener('input', renderNumbersTable);
    document.getElementById('refreshButton').addEventListener('click', loadLatestData);

    renderDashboard();
    loadLatestData();
    window.setInterval(loadLatestData, 30 * 60 * 1000);
  </script>
</body>
</html>
"""


def main() -> None:
    rows, source_mode, source_file = read_rows()
    payload = build_payload(rows, source_mode, source_file)
    app_data = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    html = HTML_TEMPLATE.replace('__APP_DATA__', app_data).replace('__RAW_CSV_URL__', RAW_CSV_URL)
    OUT_PATH.write_text(html, encoding='utf-8')
    print(f'Wrote {OUT_PATH}')
    print(f"Range: {payload['metadata']['startDateDisplay']} - {payload['metadata']['endDateDisplay']}")
    print('Top 10:', ', '.join(f"{item['number']} ({item['probability'] * 100:.2f}%)" for item in payload['top10']))


if __name__ == '__main__':
    main()
