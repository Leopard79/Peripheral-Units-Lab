// ============================================================================
// Custom Disassembled Webcam Enclosure for MG90S (Direct Gimbal Integration)
// ============================================================================
// غيّر render_mode حسب الحاجة:
//   "assembly"   : معاينة الصندوق + الغطاء + الكاميرا الوهمية واختبار الفوكس
//   "body"       : جسم الصندوق الرئيسي (05a) موجّه للطباعة بدون دعامات
//   "cover"      : الغطاء الخلفي (05b) موجّه للطباعة بدون دعامات
//   "print_plate": القطعتان معاً جاهزتان للطباعة
// ============================================================================
include <params_webcam.scad>;

render_mode   = "assembly";
show_webcam   = true;
preview_focus = 8.0;  // حرّكها بين 8.0 (فوكس بعيد للدرون) و 13.0 (فوكس قريب) للتأكد!
cover_explode = 12.0; // إبعاد الغطاء الخلفي في المعاينة (0 = مغلق تماماً)

module rrect(w, h, r=2) { offset(r=r) offset(delta=-r) square([w, h], center=true); }
module rbox2d(x0, y0, x1, y1, r=2) { translate([(x0+x1)/2, (y0+y1)/2]) rrect(x1-x0, y1-y0, r); }
module extrude_yz(x0, x1) { translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(height=x1-x0) children(); }
module extrude_xz(y0, y1) { translate([0, y1, 0]) rotate([90, 0, 0]) linear_extrude(height=y1-y0) children(); }

// ============================================================================
// PART 5A: جسم الصندوق الرئيسي مع قواعد اللوحة الأربعة وتجويف ذراع MG90S
// ============================================================================
module webcam_box_body() {
    y_horn_floor = out_y1 - mg90_horn_recess;

    union() {
        // 1. الوجه الأمامي بفتحة الأسطوانة الدوارة (24 مم)
        extrude_yz(x_front_in, x_front_out)
        difference() {
            rbox2d(out_y0, out_z0, out_y1, out_z1, 2.5);
            translate([y_shift + lens_offset_y, lens_offset_z])
                circle(d = lens_cyl_d + lens_hole_clear);
        }

        // 2. الجدار العلوي والسفلي مع ثقبي قفل الغطاء الخلفي (M2)
        for (z_pair = [[in_z1, out_z1], [out_z0, in_z0]])
        translate([0, 0, z_pair[0]])
        linear_extrude(height = z_pair[1] - z_pair[0])
        difference() {
            translate([x_rear_in, out_y0]) square([x_front_out - x_rear_in, out_y1 - out_y0]);
            translate([x_lid_screw, y_shift]) circle(d = 2.3);
        }

        // 3. الجدار الأيسر (-Y) مع فتحة خروج كابل الـ USB
        extrude_xz(out_y0, in_y0)
        difference() {
            translate([x_rear_in, out_z0]) square([x_front_out - x_rear_in, out_z1 - out_z0]);
            union() {
                translate([x_rear_in - 0.5, -cable_d/2]) square([5.0, cable_d]);
                translate([x_rear_in + 4.5, 0]) circle(d = cable_d);
            }
        }

        // 4. الجدار الأيمن (+Y) الحامل لتجويف ذراع MG90S الميكانيكي
        extrude_xz(in_y1, y_horn_floor)
        difference() {
            translate([x_rear_in, out_z0]) square([x_front_out - x_rear_in, out_z1 - out_z0]);
            translate([x_tilt_rel_pcb, 0]) circle(d = mg90_center_d);
            for (dx = [-10.5, -7.5, 7.5, 10.5])
                translate([x_tilt_rel_pcb + dx, 0]) circle(d = mg90_screw_d);
        }
        extrude_xz(y_horn_floor - 0.1, out_y1)
        difference() {
            translate([x_rear_in, out_z0]) square([x_front_out - x_rear_in, out_z1 - out_z0]);
            union() {
                translate([x_tilt_rel_pcb, 0]) circle(d = mg90_horn_hub_d);
                translate([x_tilt_rel_pcb, 0]) rrect(mg90_horn_slot_l, mg90_horn_slot_w, 1.8);
            }
        }

        // 5. القواعد الأربع الداخلية لتثبيت لوحة الكاميرا (24 × 23 مم) مع خلوص الشفة 25 مم
        extrude_yz(0, x_front_in + 0.2)
        difference() {
            intersection() {
                translate([in_y0 - 0.2, in_z0 - 0.2]) square([in_w + 0.4, in_h + 0.4]);
                union() {
                    for (sy=[-1, 1], sz=[-1, 1]) {
                        hy = y_shift + sy * pcb_hole_dx/2;
                        hz = sz * pcb_hole_dz/2;
                        cy0 = (sy < 0) ? (in_y0 - 0.2) : (hy - 3.0);
                        cy1 = (sy < 0) ? (hy + 3.0)    : (in_y1 + 0.2);
                        cz0 = (sz < 0) ? (in_z0 - 0.2) : (hz - 3.0);
                        cz1 = (sz < 0) ? (hz + 3.0)    : (in_z1 + 0.2);
                        translate([cy0, cz0]) square([cy1 - cy0, cz1 - cz0]);
                    }
                }
            }
            // تفريغ دائري واسع لحرية حركة الشفة (25 مم + سماحية 1.6 مم)
            translate([y_shift + lens_offset_y, lens_offset_z])
                circle(d = lens_flange_d + 1.6);
            // ثقوب براغي اللوحة الأربعة
            for (sy=[-1, 1], sz=[-1, 1])
                translate([y_shift + sy*pcb_hole_dx/2, sz*pcb_hole_dz/2])
                    circle(d = pcb_pilot_d);
        }
    }
}

// ============================================================================
// PART 5B: الغطاء الخلفي المندمج مع فتحات تثبيت الكابل وألسنة قفل M2
// ============================================================================
module webcam_rear_cover() {
    union() {
        // اللوح الخلفي + فتحات مرابط كابل الـ USB + فتحة تهوية
        extrude_yz(x_rear_out, x_rear_in)
        difference() {
            rbox2d(out_y0, out_z0, out_y1, out_z1, 2.5);
            rbox2d(in_y0 + 1.8, -5.2, in_y0 + 4.0, -3.2, 0.6);
            rbox2d(in_y0 + 1.8,  3.2, in_y0 + 4.0,  5.2, 0.6);
            rbox2d(y_shift + 3.0, -5.0, y_shift + 5.2, 5.0, 0.9);
        }

        // شفة المحاذاة الداخلية
        extrude_yz(x_rear_in - 0.1, x_rear_in + 2.5)
        difference() {
            translate([in_y0 + lid_tol, in_z0 + lid_tol])
                square([in_w - 2*lid_tol, in_h - 2*lid_tol]);
            translate([in_y0 + lid_tol + 2.0, in_z0 + lid_tol + 2.0])
                square([in_w - 2*lid_tol - 4.0, in_h - 2*lid_tol - 4.0]);
            translate([in_y0 - 1.0, -cable_d/2 - 0.4])
                square([4.5, cable_d + 0.8]);
        }

        // ألسنة القفل العلوية والسفلية لبراغي M2
        for (z_pair = [[in_z1 - lid_tol - 3.2, in_z1 - lid_tol],
                       [in_z0 + lid_tol,       in_z0 + lid_tol + 3.2]])
        translate([0, 0, z_pair[0]])
        linear_extrude(height = z_pair[1] - z_pair[0])
        difference() {
            rbox2d(x_rear_in - 0.1, y_shift - 4.5, x_rear_in + 5.5, y_shift + 4.5, 1.2);
            translate([x_lid_screw, y_shift]) circle(d = 1.85);
        }
    }
}

// نموذج شبحي للوحة الكاميرا والعدسة الفضية للمعاينة فقط
module ghost_webcam() {
    color("#1B8A4C", 0.85)
        translate([-pcb_thk, y_shift - pcb_w/2, -pcb_h/2])
            cube([pcb_thk, pcb_w, pcb_h]);
    color("#222222", 0.85)
        translate([0, y_shift + lens_offset_y, lens_offset_z])
            rotate([0, 90, 0]) cylinder(d=14.5, h=preview_focus + 2);
    color("#C8D0D8", 0.9)
        translate([preview_focus, y_shift + lens_offset_y, lens_offset_z])
            rotate([0, 90, 0]) {
                cylinder(d=lens_flange_d, h=lens_flange_t);
                cylinder(d=lens_cyl_d, h=15.5);
            }
}

if (render_mode == "assembly") {
    color("#C43A31", 0.82) webcam_box_body();
    translate([-cover_explode, 0, 0]) color("#374151", 0.9) webcam_rear_cover();
    if (show_webcam) ghost_webcam();
} else if (render_mode == "body") {
    translate([0, 0, x_front_out]) rotate([0, 90, 0]) webcam_box_body();
} else if (render_mode == "cover") {
    translate([0, 0, -x_rear_out]) rotate([0, -90, 0]) webcam_rear_cover();
} else if (render_mode == "print_plate") {
    translate([-24, 0, x_front_out]) rotate([0, 90, 0]) webcam_box_body();
    translate([24, 0, -x_rear_out]) rotate([0, -90, 0]) webcam_rear_cover();
}
