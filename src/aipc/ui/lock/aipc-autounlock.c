// โมดูลปลดจอล็อกเองเมื่อเห็นหน้าเจ้าของ (การ์ด 0055 ทาง ก · Pakon 2026-10-23)
//
// ทำงานในโปรแกรมจอล็อก gtklock 4.0 (โหลดด้วย -m) · ไม่ตัดสินเองว่าใช่เจ้าของไหม:
//   1. จอล็อกแล้ว → เปิดตัวเฝ้า /usr/local/sbin/aipc-face-watch (Python · ถาม visiond ทุก 2 วิ)
//   2. ตัวเฝ้าเห็นหน้าเจ้าของ → พิมพ์ "OWNER" แล้วจบ (ปล่อยกล้องให้ขั้นต่อไป)
//   3. โมดูลกด "Enter" ให้ช่องรหัสที่ว่างอยู่ (สัญญาณ activate เดียวกับคนกด) → gtklock เรียก PAM ตามปกติ →
//      PAM สแกนหน้าอีกครั้งพร้อมตรวจรูปปลอม (visiond unlock) → ผ่าน = ปลดล็อก
//   ไม่ผ่าน/ตัวเฝ้าจบเพราะอย่างอื่น → เริ่มตัวเฝ้าใหม่ แต่รอนานขึ้นทีละเท่า (5 → 10 → … ≤ 60 วิ)
// ความปลอดภัยอยู่ที่ PAM + visiond เหมือนเดิม (H7) · โมดูลแค่ "กด Enter แทน" · ช่องรหัสมีตัวอักษรอยู่ = ไม่กด
// (คนกำลังพิมพ์รหัส ต้องไม่ถูกส่งรหัสครึ่ง ๆ ไป)
//
// ไม่ include หัวไฟล์ของ GTK: บน Pi ต้องลง libgtk-3-dev ซึ่งพาแพ็กเกจใหม่ 79 ตัวและอัปเกรดไลบรารีระบบ 8 ตัว
// (ตรวจ 2026-10-23) → ประกาศเฉพาะฟังก์ชัน GLib/GTK 3 ที่ใช้ (API คงที่ของ GTK 3) แล้วลิงก์กับไลบรารีที่มีในเครื่อง

#include <signal.h>
#include <sys/types.h>

typedef int gboolean;
typedef unsigned int guint;
typedef char gchar;
typedef void *gpointer;
typedef int GPid;
typedef unsigned long GType;
typedef struct _GList { gpointer data; struct _GList *next, *prev; } GList;
typedef struct { unsigned int domain; int code; gchar *message; } GError;
typedef struct _GIOChannel GIOChannel;
typedef void GtkWidget;
typedef void GModule;
typedef gboolean (*GSourceFunc)(gpointer);
typedef gboolean (*GIOFunc)(GIOChannel *, int, gpointer);
typedef void (*GChildWatchFunc)(GPid, int, gpointer);

enum { G_IO_IN = 1, G_IO_ERR = 8, G_IO_HUP = 16 };
enum { G_IO_STATUS_NORMAL = 1 };
enum { G_SPAWN_DO_NOT_REAP_CHILD = 1 << 1 };

GList *gtk_window_list_toplevels(void);
GList *gtk_container_get_children(gpointer container);
const gchar *gtk_widget_get_name(GtkWidget *widget);
gboolean gtk_widget_is_sensitive(GtkWidget *widget);
unsigned short gtk_entry_get_text_length(gpointer entry);
GType gtk_entry_get_type(void);
GType gtk_container_get_type(void);
gboolean g_type_check_instance_is_a(gpointer instance, GType type);
void g_signal_emit_by_name(gpointer instance, const gchar *signal, ...);
void g_list_free(GList *list);
int g_strcmp0(const char *a, const char *b);
gboolean g_str_has_prefix(const gchar *str, const gchar *prefix);
void g_free(gpointer mem);
guint g_timeout_add_seconds(guint interval, GSourceFunc fn, gpointer data);
gboolean g_source_remove(guint tag);
gboolean g_spawn_async_with_pipes(const gchar *dir, gchar **argv, gchar **envp, int flags,
                                  gpointer setup, gpointer data, GPid *pid, int *in, int *out,
                                  int *err, GError **error);
void g_spawn_close_pid(GPid pid);
void g_error_free(GError *error);
guint g_child_watch_add(GPid pid, GChildWatchFunc fn, gpointer data);
GIOChannel *g_io_channel_unix_new(int fd);
void g_io_channel_set_close_on_unref(GIOChannel *ch, gboolean do_close);
int g_io_channel_read_line(GIOChannel *ch, gchar **line, gpointer len, gpointer term, GError **err);
guint g_io_add_watch(GIOChannel *ch, int cond, GIOFunc fn, gpointer data);
void g_io_channel_unref(GIOChannel *ch);

// gtklock เช็กเลขรุ่นนี้ตอนโหลด (ไม่มี = ไม่ยอมโหลด · รุ่นหลักต้องตรง 4)
const guint module_major_version = 4;
const guint module_minor_version = 0;

#ifndef WATCHER  // เทสต์บน Pi ใช้ตัวเฝ้าปลอมได้ (-DWATCHER=...) · ของจริงคงที่ ไม่รับจากที่อื่น
#define WATCHER "/usr/local/sbin/aipc-face-watch"
#endif
#define BACKOFF_MIN 5
#define BACKOFF_MAX 60

static GPid child = 0;
static guint backoff = BACKOFF_MIN;
static guint retry_source = 0;

static void start_watcher(void);

static GtkWidget *find_entry(GtkWidget *w) {
	if(g_type_check_instance_is_a(w, gtk_entry_get_type())
	   && g_strcmp0(gtk_widget_get_name(w), "input-field") == 0) return w;
	if(!g_type_check_instance_is_a(w, gtk_container_get_type())) return 0;
	GList *kids = gtk_container_get_children(w);
	GtkWidget *found = 0;
	for(GList *k = kids; k && !found; k = k->next) found = find_entry(k->data);
	g_list_free(kids);
	return found;
}

// กด Enter แทนคน · ช่องที่ใช้ได้ (ไม่ได้กำลังตรวจอยู่) และยังว่างเท่านั้น
static void press_enter(void) {
	GList *tops = gtk_window_list_toplevels();
	for(GList *t = tops; t; t = t->next) {
		GtkWidget *entry = find_entry(t->data);
		if(entry && gtk_widget_is_sensitive(entry) && gtk_entry_get_text_length(entry) == 0) {
			g_signal_emit_by_name(entry, "activate");
			break;
		}
	}
	g_list_free(tops);
}

static gboolean retry(gpointer data) {
	retry_source = 0;
	start_watcher();
	return 0;  // ไม่เรียกซ้ำ
}

static void schedule_retry(void) {
	if(retry_source) return;
	retry_source = g_timeout_add_seconds(backoff, retry, 0);
	backoff = backoff * 2 > BACKOFF_MAX ? BACKOFF_MAX : backoff * 2;
}

static gboolean on_output(GIOChannel *ch, int cond, gpointer data) {
	gchar *line = 0;
	if((cond & G_IO_IN) && g_io_channel_read_line(ch, &line, 0, 0, 0) == G_IO_STATUS_NORMAL) {
		gboolean owner = line && g_str_has_prefix(line, "OWNER");
		g_free(line);
		if(owner) press_enter();
		return 1;  // อ่านต่อ
	}
	return 0;  // ตัวเฝ้าปิดท่อ (จบแล้ว)
}

static void on_exit(GPid pid, int status, gpointer data) {
	g_spawn_close_pid(pid);
	child = 0;
	schedule_retry();  // ยังล็อกอยู่ (ถ้าปลดแล้ว gtklock จบ โมดูลก็หายไปด้วย)
}

static void start_watcher(void) {
	if(child) return;
	gchar *argv[] = { WATCHER, 0 };
	int out = -1;
	GError *err = 0;
	if(!g_spawn_async_with_pipes(0, argv, 0, G_SPAWN_DO_NOT_REAP_CHILD, 0, 0,
	                             &child, 0, &out, 0, &err)) {
		if(err) g_error_free(err);
		child = 0;
		schedule_retry();
		return;
	}
	GIOChannel *ch = g_io_channel_unix_new(out);
	g_io_channel_set_close_on_unref(ch, 1);
	g_io_add_watch(ch, G_IO_IN | G_IO_HUP | G_IO_ERR, on_output, 0);
	g_io_channel_unref(ch);
	g_child_watch_add(child, on_exit, 0);
}

// จอล็อกเสร็จแล้ว (ext-session-lock ยืนยัน) → เริ่มเฝ้า · ชนิดพารามิเตอร์ตาม module.c ของ gtklock 4.0
void on_locked(void *gtklock) {
	backoff = BACKOFF_MIN;
	start_watcher();
}

// gtklock ปิดโมดูล (ปลดล็อกแล้ว) → ปิดตัวเฝ้า กล้องดับทันที
void g_module_unload(GModule *m) {
	if(retry_source) g_source_remove(retry_source);
	if(child) kill(child, SIGTERM);
}
