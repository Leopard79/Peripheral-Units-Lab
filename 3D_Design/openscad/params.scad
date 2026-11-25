// ============================================================================
// 4-Axis Helmet-Mounted Drone Tracking Gimbal (V2) - Master Parameters
// مثبت كاميرا 4 محاور للخوذة العسكرية لرصد الدرون - ملف المتغيرات القابل للتعديل
// ============================================================================
$fn = 64;

// --- 1. سماحية الطباعة وسماكة الجدران ---
tol        = 0.4;  // سماحية الطباعة FDM (0.4 مم لفوهة 0.4)
wall       = 4.5;  // سماكة الجدران الرئيسية (MG996R)
wall_micro = 3.5;  // سماكة الجدران العلوية (MG90S والكاميرا)

// --- 2. ثقوب تثبيت القاعدة على الخوذة (عدّلها على أرض الواقع حسب خوذتك) ---
base_len_x     = 86.0;
base_wid_y     = 66.0;
base_thk       = 5.0;
helmet_hole_dx = 68.0; // المسافة الطولية بين براغي الخوذة (X)
helmet_hole_dy = 48.0; // المسافة العرضية بين براغي الخوذة (Y)
helmet_screw_d = 4.8;  // قطر الثقب (M4 مع سماحية مريحة للثقب اليدوي)  // قطر الثقب (M4)

// --- 3. ثقوب تثبيت الكاميرا على MG90S (عدّلها حسب كاميرتك) ---
cam_hole_dx = 24.0; // ثقوب اللوح السفلي (X)
cam_hole_dy = 24.0; // ثقوب اللوح السفلي (Y)
cam_back_dy = 22.0; // ثقوب اللوح الخلفي للكاميرات اللوحية PCB (Y)
cam_back_dz = 22.0; // ثقوب اللوح الخلفي العمودية (Z)
cam_screw_d = 3.2;  // قطر ثقب البرغي (M3)

// --- 4. أبعاد MG996R القياسية ---
mg996_len            = 40.7;
mg996_wid            = 19.7;
mg996_hole_dx        = 49.5;
mg996_hole_dy        = 10.0;
mg996_screw_d        = 3.4;
mg996_shaft_offset   = 10.35;
mg996_flange_to_horn = 15.5;
mg996_horn_r         = 7.5;
mg996_horn_hole_d    = 2.3;
mg996_center_d       = 7.5;

// --- 5. أبعاد 28BYJ-48 ---
step_dia          = 28.0;
step_h            = 19.0;
step_shaft_offset = 8.0;  // إزاحة المحور عن مركز الأسطوانة
step_hole_span    = 35.0;
step_screw_d      = 4.2;
step_shaft_d      = 5.0;
step_shaft_flat   = 3.0;
step_wire_w       = 15.2;
step_wire_ext     = 17.5;

// --- 6. أبعاد MG90S ---
mg90_len            = 22.8;
mg90_wid            = 12.2;
mg90_hole_span      = 27.5;
mg90_screw_d        = 2.2;
mg90_shaft_offset   = 5.4;
mg90_flange_to_horn = 10.5;

// --- 7. حساس MPU6050 والمحور المقابل ---
mpu_hole_span = 15.24;
mpu_screw_d   = 3.0;
pivot_bolt_d  = 4.2;

// --- 8. الهندسة الحركية (مفحوصة ضد التصادم لدوران 360° كامل + إمالة +-45°) ---
z_roll      = 42.0;
z_pitch_rel = 44.0;
p3_len_x    = 60.0;
p3_wid_y    = 54.0;
p2_bar_x    = 44.0;
pivot_gap   = 4.0;
yaw_tilt_z  = 28.0;

// --- قيم محسوبة تلقائياً ---
horn_gap_996  = mg996_flange_to_horn - wall;
p1_rear_in_x  = -(p2_bar_x/2 + horn_gap_996);
p1_front_in_x = +(p2_bar_x/2 + pivot_gap);
p2_pos_y_in   = +(p3_wid_y/2 + horn_gap_996);
p2_neg_y_in   = -(p3_wid_y/2 + pivot_gap);
Z_R           = z_roll;
Z_P           = z_roll + z_pitch_rel;
z_p2_bot0     = Z_R - 8.0;
z_p2_bot1     = Z_R - 3.0;
z_p3_top0     = Z_P + 3.0;
z_p3_top1     = Z_P + 7.5;
z_p4_collar0  = z_p3_top1 + 2.0;
z_p4_arm0     = Z_P + 16.5; // أعلى من جدار سيرفو الـ Pitch بـ 3 مم لضمان دوران 360° حر!
z_p4_arm1     = z_p4_arm0 + 4.0;
Z_TILT        = z_p4_arm0 + yaw_tilt_z;

// --- 9. انحناء قبة الخوذة العسكرية وأذني الأحزمة (V3 - قياسات المسطرة 10 سم) ---
ruler_half_len    = 50.0; // نصف طول المسطرة (5 سم من كل جهة)
helmet_sagitta_x  = 8.5;  // ارتفاع الفراغ أمام-خلف عند طرف المسطرة (مم)
helmet_sagitta_y  = 11.0; // ارتفاع الفراغ يمين-يسار عند طرف المسطرة (مم)
curved_t_min      = 4.5;  // أقل سماكة للقاعدة عند قمة الخوذة (مم)
adapter_t_min     = 3.2;  // أقل سماكة للقطعة الوسيطة عند قمة الخوذة (مم)
strap_slot_w      = 21.0; // عرض فتحة الحزام (لحزام 20 مم أو حبل باراكورد)
strap_slot_t      = 4.5;  // سماكة فتحة الحزام
add_strap_ears    = true; // تفعيل/إلغاء الأذنين القطرية للأحزمة

// حساب أنصاف الأقطار والقطع الناقص الثلاثي تلقائياً من قياس المسطرة:
helmet_Rx = (ruler_half_len*ruler_half_len + helmet_sagitta_x*helmet_sagitta_x) / (2 * helmet_sagitta_x);
helmet_Ry = (ruler_half_len*ruler_half_len + helmet_sagitta_y*helmet_sagitta_y) / (2 * helmet_sagitta_y);
ellip_C   = 0.5 * (helmet_Rx + helmet_Ry);
ellip_A   = ruler_half_len / sqrt(1 - pow((ellip_C - helmet_sagitta_x) / ellip_C, 2));
ellip_B   = ruler_half_len / sqrt(1 - pow((ellip_C - helmet_sagitta_y) / ellip_C, 2));
