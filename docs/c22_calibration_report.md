# C22 校准回放报告

- 生成时间：2026-10-15 19:18:23
- 模式：真实回放
- 阈值声明：高置信桶精确率 Wilson 95% 置信下界 ≥ 0.95 才允许 --enable 写门控（D2026-1009-02 第三节，首版从严）

## 指标

- 判 high：2 / 140（其中 label=true：1）
- 精确率：0.5000
- Wilson 95% 置信下界：0.0945（门槛 0.95：未达标）
- 覆盖率（high/全部）：0.0143
- 召回（high/label=true）：0.0088
- 门控文件：未写入（config/fullchain_c22.json）

## 样本明细

| # | timing | grade | label | reasons |
|---|--------|-------|-------|---------|
| 1 | 00:01:54,581 --> 00:01:56,981 | empty | True | empty_transcript |
| 2 | 00:02:38,367 --> 00:02:38,693 | low | True | speech_le_1s; speech_s=0.01 |
| 3 | 00:03:25,312 --> 00:03:43,358 | empty | True | empty_transcript |
| 4 | 00:03:51,806 --> 00:03:57,045 | empty | True | empty_transcript |
| 5 | 00:04:30,911 --> 00:04:32,658 | low | True | speech_le_1s; speech_s=0.10 |
| 6 | 00:04:42,237 --> 00:04:42,778 | low | True | speech_le_1s; speech_s=0.01 |
| 7 | 00:04:48,778 --> 00:05:02,302 | low | True | speech_le_1s; speech_s=0.50 |
| 8 | 00:05:20,470 --> 00:05:22,389 | low | True | speech_le_1s; speech_s=0.08 |
| 9 | 00:05:24,069 --> 00:05:26,949 | low | True | speech_le_1s; speech_s=0.15 |
| 10 | 00:06:38,668 --> 00:07:06,505 | low | True | avg_logprob_under |
| 11 | 00:07:07,665 --> 00:07:08,526 | empty | True | empty_transcript |
| 12 | 00:07:37,245 --> 00:07:42,625 | low | True | speech_le_1s; speech_s=0.09 |
| 13 | 00:07:47,225 --> 00:08:02,673 | low | True | speech_le_1s; speech_s=0.33 |
| 14 | 00:08:21,053 --> 00:08:22,254 | low | True | speech_le_1s; speech_s=0.29 |
| 15 | 00:08:36,293 --> 00:08:37,643 | low | True | speech_le_1s; speech_s=0.32 |
| 16 | 00:09:02,720 --> 00:09:09,481 | low | True | speech_le_1s; speech_s=0.52 |
| 17 | 00:09:13,121 --> 00:09:14,162 | low | True | speech_le_1s; speech_s=0.10 |
| 18 | 00:09:55,327 --> 00:09:59,173 | empty | True | empty_transcript |
| 19 | 00:10:27,042 --> 00:10:29,461 | low | True | speech_le_1s; speech_s=0.26 |
| 20 | 00:11:01,950 --> 00:11:02,861 | empty | False | empty_transcript |
| 21 | 00:00:53,787 --> 00:01:07,341 | low | False | speech_le_1s; speech_s=0.01 |
| 22 | 00:02:55,602 --> 00:03:02,334 | low | True | speech_le_1s; speech_s=0.40 |
| 23 | 00:04:10,461 --> 00:04:14,681 | empty | True | empty_transcript |
| 24 | 00:05:24,069 --> 00:05:43,014 | low | False | speech_le_1s; speech_s=0.08 |
| 25 | 00:05:59,077 --> 00:06:12,398 | low | False | speech_le_1s; speech_s=0.21 |
| 26 | 00:06:15,677 --> 00:06:33,757 | low | False | speech_le_1s; speech_s=0.04 |
| 27 | 00:06:36,177 --> 00:06:55,661 | low | False | speech_le_1s; speech_s=0.11 |
| 28 | 00:06:58,942 --> 00:07:19,081 | low | False | speech_le_1s; speech_s=0.09 |
| 29 | 00:07:28,201 --> 00:07:40,096 | empty | False | empty_transcript |
| 30 | 00:17:23,185 --> 00:17:25,586 | empty | True | empty_transcript |
| 31 | 00:17:31,385 --> 00:17:36,459 | empty | True | empty_transcript |
| 32 | 00:17:40,055 --> 00:17:51,221 | low | True | speech_le_1s; speech_s=0.06 |
| 33 | 00:18:00,602 --> 00:18:03,221 | empty | True | empty_transcript |
| 34 | 00:18:29,557 --> 00:18:36,986 | empty | False | empty_transcript |
| 35 | 00:19:07,286 --> 00:19:19,809 | empty | False | empty_transcript |
| 36 | 00:20:01,612 --> 00:20:07,256 | empty | False | empty_transcript |
| 37 | 00:20:27,781 --> 00:20:38,978 | empty | False | empty_transcript |
| 38 | 00:20:42,877 --> 00:20:46,540 | empty | True | empty_transcript |
| 39 | 00:20:51,005 --> 00:20:58,382 | empty | True | empty_transcript |
| 40 | 00:21:01,734 --> 00:21:06,329 | low | True | speech_le_1s; speech_s=0.12 |
| 41 | 00:00:13,279 --> 00:00:15,419 | low | True | speech_le_1s; speech_s=0.68 |
| 42 | 00:00:48,345 --> 00:00:51,985 | low | True | speech_le_1s; speech_s=0.17 |
| 43 | 00:01:14,834 --> 00:01:27,510 | low | False | speech_le_1s; speech_s=0.32 |
| 44 | 00:01:55,438 --> 00:02:02,597 | low | True | speech_le_1s; speech_s=0.01 |
| 45 | 00:02:37,710 --> 00:02:42,298 | low | True | speech_le_1s; speech_s=0.70 |
| 46 | 00:02:42,598 --> 00:03:09,485 | empty | False | empty_transcript |
| 47 | 00:03:11,665 --> 00:03:15,467 | empty | False | empty_transcript |
| 48 | 00:03:16,740 --> 00:04:06,192 | high | False |  |
| 49 | 00:04:13,569 --> 00:04:16,069 | low | True | speech_le_1s; speech_s=0.01 |
| 50 | 00:05:38,834 --> 00:05:46,793 | low | True | speech_le_1s; speech_s=0.28 |
| 51 | 00:05:55,613 --> 00:06:01,512 | low | True | speech_le_1s; speech_s=0.30 |
| 52 | 00:06:45,055 --> 00:06:49,012 | low | True | speech_le_1s; speech_s=0.88 |
| 53 | 00:07:31,302 --> 00:07:35,081 | low | False | speech_le_1s; speech_s=0.65 |
| 54 | 00:07:49,153 --> 00:07:53,185 | low | True | speech_le_1s; speech_s=0.01 |
| 55 | 00:08:38,953 --> 00:08:45,557 | low | True | speech_le_1s; speech_s=0.01 |
| 56 | 00:12:42,066 --> 00:12:45,145 | low | True | speech_le_1s; speech_s=0.47 |
| 57 | 00:17:53,746 --> 00:17:56,226 | low | True | speech_le_1s; speech_s=0.05 |
| 58 | 00:18:26,057 --> 00:18:28,258 | low | True | speech_le_1s; speech_s=0.20 |
| 59 | 00:18:35,157 --> 00:18:38,377 | empty | True | empty_transcript |
| 60 | 00:18:46,018 --> 00:18:48,074 | low | True | speech_le_1s; speech_s=0.03 |
| 61 | 00:05:03,887 --> 00:05:06,327 | low | True | speech_le_1s; speech_s=0.00 |
| 62 | 00:05:23,124 --> 00:05:30,624 | low | True | speech_le_1s; speech_s=0.61 |
| 63 | 00:06:14,257 --> 00:06:16,677 | low | True | speech_le_1s; speech_s=0.70 |
| 64 | 00:06:31,730 --> 00:06:34,970 | low | True | speech_le_1s; speech_s=0.05 |
| 65 | 00:06:52,550 --> 00:07:04,161 | low | True | speech_le_1s; speech_s=0.84 |
| 66 | 00:07:23,841 --> 00:07:24,341 | low | True | speech_le_1s; speech_s=0.12 |
| 67 | 00:10:15,851 --> 00:10:17,052 | empty | True | empty_transcript |
| 68 | 00:10:44,153 --> 00:10:44,774 | empty | True | empty_transcript |
| 69 | 00:10:48,214 --> 00:10:49,693 | empty | True | empty_transcript |
| 70 | 00:11:58,758 --> 00:12:03,638 | low | True | speech_le_1s; speech_s=0.26 |
| 71 | 00:13:11,980 --> 00:13:22,820 | low | True | speech_le_1s; speech_s=0.21 |
| 72 | 00:13:26,860 --> 00:13:32,960 | low | True | speech_le_1s; speech_s=0.33 |
| 73 | 00:14:20,981 --> 00:14:22,422 | low | True | speech_le_1s; speech_s=0.04 |
| 74 | 00:14:26,361 --> 00:14:27,682 | low | True | speech_le_1s; speech_s=0.08 |
| 75 | 00:14:39,562 --> 00:14:43,470 | low | True | speech_le_1s; speech_s=0.15 |
| 76 | 00:15:09,279 --> 00:15:10,144 | low | True | speech_le_1s; speech_s=0.04 |
| 77 | 00:15:18,563 --> 00:15:26,159 | high | True |  |
| 78 | 00:15:28,659 --> 00:15:29,720 | low | True | speech_le_1s; speech_s=0.01 |
| 79 | 00:15:43,426 --> 00:15:44,485 | low | True | speech_le_1s; speech_s=0.02 |
| 80 | 00:15:57,306 --> 00:16:01,125 | low | True | speech_le_1s; speech_s=0.05 |
| 81 | 00:00:26,083 --> 00:00:31,164 | low | True | no_speech_prob_over |
| 82 | 00:00:49,152 --> 00:02:15,262 | low | True | speech_le_1s; speech_s=0.17 |
| 83 | 00:02:21,581 --> 00:02:28,801 | low | True | speech_le_1s; speech_s=0.07 |
| 84 | 00:02:32,081 --> 00:07:31,790 | empty | True | empty_transcript |
| 85 | 00:07:59,805 --> 00:08:12,245 | low | True | speech_le_1s; speech_s=0.01 |
| 86 | 00:08:38,354 --> 00:08:42,394 | low | False | speech_le_1s; speech_s=0.03 |
| 87 | 00:09:07,590 --> 00:09:15,201 | low | True | speech_le_1s; speech_s=0.18 |
| 88 | 00:09:17,562 --> 00:09:19,142 | low | True | speech_le_1s; speech_s=0.02 |
| 89 | 00:09:23,201 --> 00:09:29,542 | low | True | speech_le_1s; speech_s=0.38 |
| 90 | 00:09:32,053 --> 00:09:34,522 | low | True | speech_le_1s; speech_s=0.26 |
| 91 | 00:09:39,341 --> 00:09:42,701 | low | True | no_speech_prob_over |
| 92 | 00:09:50,221 --> 00:09:58,570 | low | True | speech_le_1s; speech_s=0.30 |
| 93 | 00:10:02,429 --> 00:10:03,269 | empty | True | empty_transcript |
| 94 | 00:10:07,149 --> 00:10:16,149 | low | True | no_speech_prob_over |
| 95 | 00:10:35,885 --> 00:10:46,046 | low | True | no_speech_prob_over |
| 96 | 00:10:58,576 --> 00:10:59,755 | low | True | speech_le_1s; speech_s=0.80 |
| 97 | 00:11:13,956 --> 00:11:15,015 | low | True | speech_le_1s; speech_s=0.70 |
| 98 | 00:11:36,717 --> 00:11:43,258 | empty | True | empty_transcript |
| 99 | 00:11:46,538 --> 00:12:01,173 | empty | True | empty_transcript |
| 100 | 00:12:07,693 --> 00:12:11,629 | low | True | speech_le_1s; speech_s=0.27 |
| 101 | 00:00:25,940 --> 00:00:27,327 | low | True | speech_le_1s; speech_s=0.00 |
| 102 | 00:03:28,217 --> 00:03:30,174 | empty | False | empty_transcript |
| 103 | 00:03:43,961 --> 00:03:45,762 | empty | True | empty_transcript |
| 104 | 00:04:01,403 --> 00:04:05,883 | low | True | speech_le_1s; speech_s=0.99 |
| 105 | 00:04:19,184 --> 00:04:21,603 | empty | True | empty_transcript |
| 106 | 00:04:59,500 --> 00:05:09,761 | low | False | speech_le_1s; speech_s=0.67 |
| 107 | 00:05:28,245 --> 00:05:29,038 | low | True | speech_le_1s; speech_s=0.03 |
| 108 | 00:05:40,077 --> 00:05:42,401 | low | True | speech_le_1s; speech_s=0.11 |
| 109 | 00:06:51,744 --> 00:06:58,290 | empty | True | empty_transcript |
| 110 | 00:07:00,990 --> 00:07:04,610 | empty | True | empty_transcript |
| 111 | 00:07:06,550 --> 00:07:10,233 | low | True | speech_le_1s; speech_s=0.17 |
| 112 | 00:07:13,730 --> 00:07:16,370 | low | True | speech_le_1s; speech_s=0.13 |
| 113 | 00:07:22,043 --> 00:07:26,584 | low | True | speech_le_1s; speech_s=0.76 |
| 114 | 00:07:32,663 --> 00:07:34,124 | low | True | speech_le_1s; speech_s=0.59 |
| 115 | 00:07:38,944 --> 00:07:43,949 | empty | True | empty_transcript |
| 116 | 00:07:56,050 --> 00:08:03,009 | empty | True | empty_transcript |
| 117 | 00:08:23,069 --> 00:08:28,189 | empty | True | empty_transcript |
| 118 | 00:08:35,590 --> 00:08:40,009 | low | True | speech_le_1s; speech_s=0.10 |
| 119 | 00:08:53,169 --> 00:08:55,850 | low | True | speech_le_1s; speech_s=0.84 |
| 120 | 00:08:57,389 --> 00:09:00,289 | low | False | speech_le_1s; speech_s=0.45 |
| 121 | 00:00:14,140 --> 00:00:29,486 | empty | False | empty_transcript |
| 122 | 00:00:35,765 --> 00:00:53,658 | low | False | avg_logprob_under |
| 123 | 00:00:57,438 --> 00:00:59,118 | low | True | speech_le_1s; speech_s=0.10 |
| 124 | 00:01:04,415 --> 00:01:10,721 | empty | True | empty_transcript |
| 125 | 00:01:23,281 --> 00:01:24,682 | low | True | speech_le_1s; speech_s=0.09 |
| 126 | 00:01:36,121 --> 00:01:41,841 | low | True | speech_le_1s; speech_s=0.01 |
| 127 | 00:01:45,641 --> 00:01:48,042 | empty | True | empty_transcript |
| 128 | 00:01:51,421 --> 00:02:23,465 | low | True | speech_le_1s; speech_s=0.77 |
| 129 | 00:02:26,069 --> 00:02:34,870 | low | False | speech_le_1s; speech_s=0.74 |
| 130 | 00:02:38,213 --> 00:02:54,157 | empty | False | empty_transcript |
| 131 | 00:02:57,402 --> 00:03:10,961 | low | False | speech_le_1s; speech_s=0.04 |
| 132 | 00:03:15,158 --> 00:03:15,949 | low | True | speech_le_1s; speech_s=0.07 |
| 133 | 00:03:38,937 --> 00:03:41,117 | empty | True | empty_transcript |
| 134 | 00:04:00,018 --> 00:04:01,258 | low | True | speech_le_1s; speech_s=0.03 |
| 135 | 00:04:28,338 --> 00:04:37,622 | empty | True | empty_transcript |
| 136 | 00:05:35,744 --> 00:05:57,697 | empty | True | empty_transcript |
| 137 | 00:06:10,240 --> 00:06:16,057 | empty | False | empty_transcript |
| 138 | 00:06:24,677 --> 00:06:34,218 | empty | True | empty_transcript |
| 139 | 00:06:36,358 --> 00:06:57,278 | empty | True | empty_transcript |
| 140 | 00:07:10,233 --> 00:07:26,689 | low | True | speech_le_1s; speech_s=0.06 |
