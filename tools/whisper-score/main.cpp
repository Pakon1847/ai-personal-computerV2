// aipc-whisper-score: ฟังเสียงครั้งเดียว แล้วให้คะแนนประโยคที่เป็นไปได้ (การ์ด 0026 · spike)
//
// ทำไม: whisper ถอดอิสระแล้วได้ "เป๊ก" จาก "ปิดแท็บ" · ถ้าให้ whisper ตอบว่า "เสียงนี้ตรงกับประโยค X แค่ไหน"
// (คะแนน = log ความน่าจะเป็นของทุกคำในประโยค + จบประโยค) แล้วเลือกคำสั่งที่คะแนนสูงสุด จะทนเสียงไม่ชัดได้ดีกว่า ·
// เทียบกับคะแนนของประโยคที่ถอดอิสระ → ถ้าคำสั่งที่ดีที่สุดยังห่างมาก = ไม่ใช่คำสั่ง (ส่งไปแชท) หรือไม่มั่นใจ (ถามใหม่)
//
// โหลดโมเดลครั้งเดียวแล้วรอคำขอทาง stdin (ไม่เปิดพอร์ต) · คำขอหนึ่งชุด:
//   WAV <ไฟล์ 16 kHz 16-bit>        เข้ารหัสเสียง + ถอดอิสระ (greedy · audio_ctx ตามความยาวเสียง)
//   PROMPT <ข้อความ>                (ไม่ใส่ก็ได้) คำนำที่ใช้ทั้งตอนถอดอิสระและตอนให้คะแนน
//   FIX <ข้อความ>                   ให้คะแนนประโยคนี้ทั้งประโยค
//   PRE <ข้อความ>                   บังคับขึ้นต้นด้วยข้อความนี้ แล้วให้ whisper ถอดต่อเอง (คำค้นหา ฯลฯ)
//   GO                              ทำ แล้วตอบ JSON หนึ่งบรรทัด
//   AGAIN                           ให้คะแนน FIX/PRE ชุดใหม่บนเสียงเดิม (ไม่เข้ารหัสซ้ำ · สร้างตัวเลือกจากข้อความที่ถอดอิสระได้)
#include "whisper.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>
#include <string>
#include <vector>

using clk = std::chrono::steady_clock;

static double ms_since(clk::time_point t) {
    return std::chrono::duration<double, std::milli>(clk::now() - t).count();
}

static bool read_wav(const std::string & path, std::vector<float> & pcm) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;
    std::vector<char> b((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    if (b.size() < 44 || memcmp(b.data(), "RIFF", 4) != 0 || memcmp(b.data() + 8, "WAVE", 4) != 0) return false;
    size_t pos = 12, off = 0, len = 0;
    int ch = 0, rate = 0, bits = 0;
    while (pos + 8 <= b.size()) {
        uint32_t n;
        memcpy(&n, b.data() + pos + 4, 4);
        if (memcmp(b.data() + pos, "fmt ", 4) == 0 && pos + 24 <= b.size()) {
            uint16_t c, bps;
            uint32_t sr;
            memcpy(&c, b.data() + pos + 10, 2);
            memcpy(&sr, b.data() + pos + 12, 4);
            memcpy(&bps, b.data() + pos + 22, 2);
            ch = c; rate = (int) sr; bits = bps;
        } else if (memcmp(b.data() + pos, "data", 4) == 0) {
            off = pos + 8;
            len = std::min<size_t>(n, b.size() - off);  // pw-record ที่ยังอัดอยู่ใส่ขนาดไม่ครบ
            break;
        }
        pos += 8 + (size_t) n + (n & 1);
    }
    if (off == 0 || rate != 16000 || bits != 16 || ch < 1) return false;
    const size_t frames = len / 2 / ch;
    const int16_t * s = (const int16_t *) (b.data() + off);
    pcm.resize(frames);
    for (size_t i = 0; i < frames; i++) {
        int acc = 0;
        for (int c = 0; c < ch; c++) acc += s[i * ch + c];
        pcm[i] = acc / (32768.0f * ch);
    }
    return true;
}

// ตัดไบต์ที่ไม่ครบตัวอักษร (ตัวไทย = 3 ไบต์ · whisper ตัดกลางตัวได้ตอนหยุดถอด) → JSON อ่านได้เสมอ
static std::string utf8_valid(const std::string & s) {
    std::string o;
    for (size_t i = 0; i < s.size();) {
        const unsigned char c = s[i];
        const size_t n = c < 0x80 ? 1 : (c >> 5) == 0x6 ? 2 : (c >> 4) == 0xE ? 3 : (c >> 3) == 0x1E ? 4 : 0;
        bool ok = n > 0 && i + n <= s.size();
        for (size_t k = 1; ok && k < n; k++) ok = ((unsigned char) s[i + k] >> 6) == 0x2;
        if (ok) { o.append(s, i, n); i += n; } else { i++; }
    }
    return o;
}

static std::string jstr(const std::string & raw) {
    const std::string s = utf8_valid(raw);
    std::string o = "\"";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') { o += '\\'; o += (char) c; }
        else if (c == '\n') o += "\\n";
        else if (c < 0x20) { char t[8]; snprintf(t, sizeof t, "\\u%04x", c); o += t; }
        else o += (char) c;
    }
    return o + "\"";
}

struct Scorer {
    whisper_context * ctx;
    whisper_state * st;
    int n_threads;
    int eot, n_vocab;
    std::vector<whisper_token> prefix;   // [prev + คำนำ] + SOT th transcribe notimestamps
    std::vector<float> prefix_logits;    // logits หลังคำนำ (ใช้ซ้ำทุกประโยค)
    int n_decode = 0;                    // จำนวนครั้งที่เรียกตัวถอด (ดูความเร็ว)

    // log-softmax เฉพาะโทเค็นข้อความ + EOT (ตัดโทเค็นพิเศษ/เวลา เหมือนตอนถอดจริงที่ห้ามไว้)
    float lse(const float * lg) const {
        float mx = -INFINITY;
        for (int i = 0; i <= eot; i++) mx = std::max(mx, lg[i]);
        double s = 0;
        for (int i = 0; i <= eot; i++) s += std::exp((double) lg[i] - mx);
        return mx + (float) std::log(s);
    }

    // ถอด t ต่อจาก n_past · out = logits แถวสุดท้าย · rows = ทุกแถว (whisper.cpp แก้ 1 บรรทัดให้คืนทุกแถว)
    const float * decode(const std::vector<whisper_token> & t, int n_past, std::vector<float> & out) {
        n_decode++;
        if (whisper_decode_with_state(ctx, st, t.data(), (int) t.size(), n_past, n_threads) != 0) return nullptr;
        const float * lg = whisper_get_logits_from_state(st);
        out.assign(lg + (t.size() - 1) * (size_t) n_vocab, lg + t.size() * (size_t) n_vocab);
        return lg;
    }

    bool set_prefix(const std::string & prompt) {
        prefix.clear();
        if (!prompt.empty()) {
            std::vector<whisper_token> p(512);
            int n = whisper_tokenize(ctx, (" " + prompt).c_str(), p.data(), (int) p.size());
            if (n < 0) return false;
            prefix.push_back(whisper_token_prev(ctx));
            prefix.insert(prefix.end(), p.begin(), p.begin() + n);
        }
        prefix.push_back(whisper_token_sot(ctx));
        prefix.push_back(whisper_token_lang(ctx, whisper_lang_id("th")));
        prefix.push_back(whisper_token_transcribe(ctx));
        prefix.push_back(whisper_token_not(ctx));
        return decode(prefix, 0, prefix_logits) != nullptr;
    }

    std::vector<whisper_token> tokenize(const std::string & text) {
        std::vector<whisper_token> t(256);
        int n = whisper_tokenize(ctx, text.c_str(), t.data(), (int) t.size());
        t.resize(n > 0 ? n : 0);
        return t;
    }

    // คะแนนของ toks ต่อด้วย EOT (ถอดทั้งประโยคในครั้งเดียว) · max_more>0 = ถอดต่อเองหลัง toks (greedy) จนจบ
    bool score(const std::vector<whisper_token> & toks, int max_more, float & lp, std::vector<whisper_token> & out_toks) {
        std::vector<float> row = prefix_logits;
        int n_past = (int) prefix.size();
        lp = 0;
        if (!toks.empty()) {
            lp += row[toks[0]] - lse(row.data());
            const float * lg = decode(toks, n_past, row);
            if (!lg) return false;
            for (size_t i = 1; i < toks.size(); i++) {
                const float * r = lg + (i - 1) * (size_t) n_vocab;
                lp += r[toks[i]] - lse(r);
            }
            n_past += (int) toks.size();
        }
        out_toks = toks;
        for (int k = 0; k < max_more; k++) {
            int best = 0;
            for (int i = 1; i <= eot; i++) if (row[i] > row[best]) best = i;
            if (best == eot) break;
            lp += row[best] - lse(row.data());
            out_toks.push_back(best);
            if (!decode({best}, n_past++, row)) return false;
        }
        lp += row[eot] - lse(row.data());
        return true;
    }

    std::string text(const std::vector<whisper_token> & t) const {
        std::string s;
        for (whisper_token x : t) if (x < eot) s += whisper_token_to_str(ctx, x);
        return s;
    }
};

// ให้คะแนนตัวเลือกทุกตัว → JSON (ไม่มีวงเล็บเหลี่ยม) · FIX ถอดรวดเดียว · PRE ถอดต่อเองทีละคำ (ช้ากว่ามาก)
static std::string score_all(Scorer & sc, const std::vector<std::pair<char, std::string>> & cands) {
    std::string out;
    for (size_t c = 0; c < cands.size(); c++) {
        float lp;
        std::vector<whisper_token> got;
        const bool ok = sc.score(sc.tokenize(cands[c].second), cands[c].first == 'P' ? 32 : 0, lp, got);
        if (c) out += ",";
        out += "{\"lp\":" + (ok ? std::to_string(lp) : std::string("null")) + ",\"n\":" +
               std::to_string(got.size()) + (cands[c].first == 'P' ? ",\"text\":" + jstr(sc.text(got)) : "") + "}";
    }
    return out;
}

int main(int argc, char ** argv) {
    if (argc < 2) {
        fprintf(stderr, "ใช้: %s <โมเดล ggml> [เธรด]\n", argv[0]);
        return 2;
    }
    whisper_log_set([](enum ggml_log_level, const char *, void *) {}, nullptr);
    const int n_threads = argc > 2 ? atoi(argv[2]) : 4;
    auto t_load = clk::now();
    whisper_context_params cp = whisper_context_default_params();
    whisper_context * ctx = whisper_init_from_file_with_params(argv[1], cp);
    if (!ctx) { fprintf(stderr, "โหลดโมเดลไม่ได้\n"); return 1; }
    // ชุดความจำ (state) แยกตามขนาดหน้าต่างเสียง: whisper.cpp 1.9.4 ถอดเพี้ยนถ้าเปลี่ยน audio_ctx บน state เดิม
    // (วัด 2026-10-14: ขนาดเดิมผลซ้ำได้ทุกครั้ง · สลับขนาดแล้วได้ "ม ม ม …")
    std::map<int, whisper_state *> states;
    const int buckets[] = {192, 256, 384, 512, 768, 1500};
    Scorer sc{ctx, nullptr, n_threads, whisper_token_eot(ctx), whisper_n_vocab(ctx), {}, {}};
    printf("{\"ready\":true,\"load_ms\":%.0f}\n", ms_since(t_load));
    fflush(stdout);

    std::string line, wav, prompt;
    std::vector<std::pair<char, std::string>> cands;  // 'F' = FIX · 'P' = PRE
    bool have_audio = false;  // AGAIN ใช้ได้หลัง GO ที่สำเร็จเท่านั้น
    while (std::getline(std::cin, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.rfind("WAV ", 0) == 0) wav = line.substr(4);
        else if (line.rfind("PROMPT ", 0) == 0) prompt = line.substr(7);
        else if (line.rfind("FIX ", 0) == 0) cands.push_back({'F', line.substr(4)});
        else if (line.rfind("PRE ", 0) == 0) cands.push_back({'P', line.substr(4)});
        else if (line == "AGAIN") {
            // state ล่าสุดยังเก็บผลเข้ารหัสเสียงไว้ (cross-attention) และ prefix_logits ยังเป็นของเสียงนี้
            if (!have_audio) {
                printf("{\"error\":\"ยังไม่มีเสียง\"}\n");
            } else {
                auto t1 = clk::now();
                sc.n_decode = 0;
                std::string out = "{\"cands\":[" + score_all(sc, cands) + "],\"score_ms\":" +
                                  std::to_string((int) ms_since(t1)) + ",\"n_decode\":" + std::to_string(sc.n_decode) + "}";
                printf("%s\n", out.c_str());
            }
            fflush(stdout);
            cands.clear();
        }
        else if (line == "GO") {
            have_audio = false;
            auto t0 = clk::now();
            std::vector<float> pcm;
            if (!read_wav(wav, pcm)) {
                printf("{\"error\":\"อ่านไฟล์เสียงไม่ได้\"}\n");
            } else {
                const double secs = pcm.size() / 16000.0;
                // หน้าต่างเสียงพอดีความยาว + 1.5 วิ (สั้นเกินทำให้ whisper วนซ้ำ · วัด 2026-10-14) · ปัดขึ้นทีละ 64
                const int need = (int) std::ceil((secs + 1.5) * 50.0);
                int actx = 1500;
                for (int b : buckets) if (b >= need) { actx = b; break; }
                double state_ms = 0;
                if (!states.count(actx)) {
                    auto ts = clk::now();
                    states[actx] = whisper_init_state(ctx);
                    state_ms = ms_since(ts);
                }
                whisper_state * st = states[actx];
                sc.st = st;
                sc.n_decode = 0;
                whisper_full_params fp = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
                fp.n_threads = n_threads;
                fp.language = "th";
                fp.no_timestamps = true;
                fp.single_segment = getenv("AIPC_SS") ? atoi(getenv("AIPC_SS")) != 0 : false;
                fp.no_context = true;
                fp.print_progress = fp.print_realtime = fp.print_special = fp.print_timestamps = false;
                fp.audio_ctx = actx;
                fp.max_tokens = getenv("AIPC_MAXTOK") ? atoi(getenv("AIPC_MAXTOK")) : 0;
                fp.temperature_inc = 0.0f;  // ไม่ถอดซ้ำด้วยอุณหภูมิอื่น (เร็ว · ผลซ้ำได้)
                fp.initial_prompt = prompt.empty() ? nullptr : prompt.c_str();
                const int rc = whisper_full_with_state(ctx, st, fp, pcm.data(), (int) pcm.size());
                const double full_ms = ms_since(t0);
                std::vector<whisper_token> free_toks;
                float free_plog = 0;
                if (rc == 0) {
                    for (int s = 0; s < whisper_full_n_segments_from_state(st); s++)
                        for (int i = 0; i < whisper_full_n_tokens_from_state(st, s); i++) {
                            whisper_token_data d = whisper_full_get_token_data_from_state(st, s, i);
                            if (d.id < sc.eot) { free_toks.push_back(d.id); free_plog += d.plog; }
                        }
                }
                auto t1 = clk::now();
                std::string out = "{\"secs\":" + std::to_string(secs) + ",\"actx\":" + std::to_string(actx) +
                                  ",\"full_ms\":" + std::to_string((int) full_ms) +
                                  ",\"state_ms\":" + std::to_string((int) state_ms);
                if (rc != 0 || !sc.set_prefix(prompt)) {
                    out += ",\"error\":\"ถอดไม่สำเร็จ\"}";
                } else {
                    float lp_free;
                    std::vector<whisper_token> tmp;
                    sc.score(free_toks, 0, lp_free, tmp);
                    const std::string free_text = sc.text(free_toks);
                    float lp_retok;
                    sc.score(sc.tokenize(free_text), 0, lp_retok, tmp);
                    out += ",\"text\":" + jstr(free_text) + ",\"free\":" + std::to_string(lp_free) +
                           ",\"free_retok\":" + std::to_string(lp_retok) + ",\"free_n\":" + std::to_string(free_toks.size()) +
                           ",\"cands\":[";
                    out += score_all(sc, cands) + "],\"score_ms\":" + std::to_string((int) ms_since(t1)) +
                           ",\"n_decode\":" + std::to_string(sc.n_decode) + "}";
                    have_audio = true;
                }
                printf("%s\n", out.c_str());
            }
            fflush(stdout);
            wav.clear(); prompt.clear(); cands.clear();
        }
    }
    for (auto & kv : states) whisper_free_state(kv.second);
    whisper_free(ctx);
    return 0;
}
