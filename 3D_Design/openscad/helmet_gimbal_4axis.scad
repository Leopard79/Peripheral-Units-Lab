// ============================================================================
// 4-Axis Helmet-Mounted Drone Tracking Gimbal (V2) - Parametric OpenSCAD
// ============================================================================
include <params.scad>;

render_mode   = "assembly"; // "assembly" | "print_plate" | "part1".."part5"
show_motors   = true;

// زوايا اختبار الحركة
preview_roll  = 0;   // [-45 .. +45]
preview_pitch = 0;   // [-45 .. +45]
preview_yaw   = 0;   // [0 .. 360]
preview_tilt  = 30;  // [-15 .. +85]

module rrect(w, h, r=2) { offset(r=r) offset(delta=-r) square([w, h], center=true); }
module rbox2d(x0, y0, x1, y1, r=2) { translate([(x0+x1)/2, (y0+y1)/2]) rrect(x1-x0, y1-y0, r); }
module double_d_2d(d, flat) { intersection() { circle(d=d); square([d*2, flat], center=true); } }

module extrude_yz(x0, x1) {
    translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(height = x1 - x0) children();
}
module extrude_xz(y0, y1) {
    translate([0, y1, 0]) rotate([90, 0, 0]) linear_extrude(height = y1 - y0) children();
}

module part1_helmet_base() {
    mg_cut_w = mg996_wid + tol;
    mg_cut_h = mg996_len + tol;
    z_body_c = Z_R - mg996_shaft_offset;
    union() {
        translate([0, 0, -base_thk]) linear_extrude(height = base_thk)
        difference() {
            rrect(base_len_x, base_wid_y, 5);
            for (sx=[-1, 1], sy=[-1, 1])
                translate([sx*helmet_hole_dx/2, sy*helmet_hole_dy/2]) circle(d=helmet_screw_d);
            rrect(24, 12, 3);
        }
        extrude_yz(p1_rear_in_x - wall, p1_rear_in_x)
        difference() {
            rbox2d(-18, -1, 18, 62, 4);
            translate([0, z_body_c]) square([mg_cut_w, mg_cut_h], center=true);
            for (sy=[-1, 1], sz=[-1, 1])
                translate([sy*mg996_hole_dy/2, z_body_c + sz*mg996_hole_dx/2]) circle(d=mg996_screw_d);
        }
        extrude_yz(p1_front_in_x, p1_front_in_x + wall)
        difference() {
            union() { rbox2d(-14, -1, 14, Z_R, 2); translate([0, Z_R]) circle(d=22); }
            translate([0, Z_R]) circle(d=pivot_bolt_d);
        }
        for (y_pos = [-13, 9])
        extrude_xz(y_pos, y_pos + 4)
            polygon([[p1_front_in_x+wall-0.5, -1], [p1_front_in_x+wall-0.5, 24], [p1_front_in_x+wall+10, -1]]);
    }
}

module part2_roll_u_frame() {
    mg_cut_w   = mg996_wid + tol;
    mg_cut_h   = mg996_len + tol;
    x_p_body_c = -mg996_shaft_offset;
    union() {
        translate([0, 0, z_p2_bot0]) linear_extrude(height = z_p2_bot1 - z_p2_bot0)
        difference() {
            rbox2d(-p2_bar_x/2, p2_neg_y_in - wall, p2_bar_x/2, p2_pos_y_in + wall, 3);
            rrect(20, 28, 4);
        }
        extrude_yz(-p2_bar_x/2, -p2_bar_x/2 + wall)
        difference() {
            union() { rbox2d(-13, z_p2_bot0, 13, Z_R, 2); translate([0, Z_R]) circle(d=26); }
            translate([0, Z_R]) circle(d=mg996_center_d);
            for (ang = [0, 90, 180, 270])
                translate([mg996_horn_r*cos(ang), Z_R + mg996_horn_r*sin(ang)]) circle(d=mg996_horn_hole_d);
        }
        extrude_yz(p2_bar_x/2 - wall, p2_bar_x/2)
        difference() {
            union() { rbox2d(-11, z_p2_bot0, 11, Z_R, 2); translate([0, Z_R]) circle(d=22); }
            translate([0, Z_R]) circle(d=pivot_bolt_d);
        }
        // جدار +Y: محرك Pitch MG996R مركب أفقياً لتوفير خلوص علوي كامل لدوران 360°!
        extrude_xz(p2_pos_y_in, p2_pos_y_in + wall)
        difference() {
            union() {
                rbox2d(-22, z_p2_bot0, 22, Z_P + 13.5, 3);
                rbox2d(-41, Z_P - 13.5, 22, Z_P + 13.5, 4);
                polygon([[-22, z_p2_bot0], [-40, Z_P - 13.0], [-20, Z_P - 13.0]]);
            }
            translate([x_p_body_c, Z_P]) square([mg_cut_h, mg_cut_w], center=true);
            for (sx=[-1, 1], sz=[-1, 1])
                translate([x_p_body_c + sx*mg996_hole_dx/2, Z_P + sz*mg996_hole_dy/2]) circle(d=mg996_screw_d);
        }
        extrude_xz(p2_neg_y_in - wall, p2_neg_y_in)
        difference() {
            union() { rbox2d(-14, z_p2_bot0, 14, Z_P, 2); translate([0, Z_P]) circle(d=26); }
            translate([0, Z_P]) circle(d=pivot_bolt_d);
        }
    }
}

module part3_pitch_platform() {
    cx_step = -step_shaft_offset;
    union() {
        translate([0, 0, z_p3_top0]) linear_extrude(height = z_p3_top1 - z_p3_top0)
        difference() {
            rrect(p3_len_x, p3_wid_y, 4);
            translate([cx_step, 0]) circle(d = step_dia + tol + 0.2);
            translate([cx_step - (step_wire_ext + 0.5)/2, 0])
                square([step_wire_ext + 0.5, step_wire_w + 0.6], center=true);
            translate([cx_step, +step_hole_span/2]) circle(d=step_screw_d);
            translate([cx_step, -step_hole_span/2]) circle(d=step_screw_d);
            translate([18, +mpu_hole_span/2]) circle(d=mpu_screw_d);
            translate([18, -mpu_hole_span/2]) circle(d=mpu_screw_d);
            translate([10.0, -21.0]) circle(d=2.2);
            translate([16.5, -21.0]) circle(d=2.2);
        }
        extrude_xz(p3_wid_y/2 - wall, p3_wid_y/2)
        difference() {
            union() { rbox2d(-13, Z_P, 13, z_p3_top1, 2); translate([0, Z_P]) circle(d=26); }
            translate([0, Z_P]) circle(d=mg996_center_d);
            for (ang = [0, 90, 180, 270])
                translate([mg996_horn_r*sin(ang), Z_P + mg996_horn_r*cos(ang)]) circle(d=mg996_horn_hole_d);
        }
        extrude_xz(-p3_wid_y/2, -p3_wid_y/2 + wall)
        difference() {
            union() { rbox2d(-11, Z_P, 11, z_p3_top1, 2); translate([0, Z_P]) circle(d=22); }
            translate([0, Z_P]) circle(d=pivot_bolt_d);
        }
    }
}

module part4_yaw_hub() {
    z_mg90_c   = Z_TILT - mg90_shaft_offset;
    mg90_cut_w = mg90_wid + tol;
    mg90_cut_h = mg90_len + tol;
    union() {
        translate([0, 0, z_p4_collar0]) linear_extrude(height = 4.0)
        difference() {
            union() { circle(d=18); rbox2d(-3, -20, 3, -6, 1.5); }
            double_d_2d(step_shaft_d + tol, step_shaft_flat + tol);
        }
        translate([0, 0, z_p4_collar0 + 3.5]) linear_extrude(height = z_p4_arm0 - z_p4_collar0 - 3.0)
        difference() {
            circle(d=18);
            double_d_2d(step_shaft_d + tol, step_shaft_flat + tol);
        }
        translate([0, 0, z_p4_arm0]) linear_extrude(height = 4.0)
        difference() {
            union() { circle(d=22); rbox2d(-11, 0, 11, 27, 3); }
            double_d_2d(step_shaft_d + tol, step_shaft_flat + tol);
        }
        extrude_xz(23.5, 27.0)
        difference() {
            rbox2d(-11, z_p4_arm0, 11, z_mg90_c + 18, 3);
            translate([0, z_mg90_c]) square([mg90_cut_w, mg90_cut_h], center=true);
            translate([0, z_mg90_c - mg90_hole_span/2]) circle(d=mg90_screw_d);
            translate([0, z_mg90_c + mg90_hole_span/2]) circle(d=mg90_screw_d);
        }
        for (x_pos = [-10.5, 7.5])
        extrude_yz(x_pos, x_pos + 3.0)
            polygon([[10, z_p4_arm1 - 0.5], [24, z_p4_arm1 - 0.5], [24, z_p4_arm1 + 15]]);
    }
}

module part5_camera_bracket() {
    z_c_bot0 = Z_TILT - 13.5;
    z_c_bot1 = Z_TILT - 10.0;
    union() {
        translate([0, 0, z_c_bot0]) linear_extrude(height = z_c_bot1 - z_c_bot0)
        difference() {
            rbox2d(-17, -18, 17, 16.5, 3);
            for (sx=[-1, 1], sy=[-1, 1])
                translate([sx*cam_hole_dx/2, sy*cam_hole_dy/2 - 1.0]) circle(d=cam_screw_d);
            translate([0, -1.0]) rrect(16, 5, 2.2);
        }
        extrude_yz(-17.0, -13.5)
        difference() {
            rbox2d(-18, z_c_bot0, 16.5, Z_TILT + 16, 3);
            for (sy=[-1, 1], sz=[-1, 1])
                translate([sy*cam_back_dy/2 - 0.75, Z_TILT + 2.0 + sz*cam_back_dz/2]) circle(d=cam_screw_d);
            translate([-0.75, Z_TILT + 2.0]) circle(d=10);
        }
        extrude_xz(13.0, 16.5)
        difference() {
            union() { rbox2d(-17, z_c_bot0, 9, Z_TILT + 2, 2); translate([0, Z_TILT]) circle(d=18); }
            translate([0, Z_TILT]) circle(d=5.2);
            for (dx = [-11.0, -7.5, 7.5]) translate([dx, Z_TILT]) circle(d=2.0);
        }
    }
}


// ============================================================================
// V3 CURVED HELMET SADDLE & STRAP EARS (مطابقة لانحناء الخوذة 8.5 / 11.0 مم)
// ============================================================================
module helmet_dual_footprint_2d() {
    difference() {
        union() {
            rrect(base_len_x, base_wid_y, 5);
            if (add_strap_ears) {
                for (sx=[-1, 1], sy=[-1, 1]) {
                    ang = atan2(sy * 33.0, sx * 43.0);
                    translate([sx * 43.0, sy * 33.0])
                        rotate([0, 0, ang])
                            rbox2d(-10, -15.5, 13.5, 15.5, 4);
                }
            }
        }
        // فتحات الأحزمة القطرية الأربع
        if (add_strap_ears) {
            for (sx=[-1, 1], sy=[-1, 1]) {
                ang = atan2(sy * 33.0, sx * 43.0);
                translate([sx * 43.0, sy * 33.0])
                    rotate([0, 0, ang])
                        rbox2d(2.5, -strap_slot_w/2, 2.5 + strap_slot_t, strap_slot_w/2, 1.8);
            }
        }
        // ثقوب البراغي الأربعة M4
        for (sx=[-1, 1], sy=[-1, 1])
            translate([sx*helmet_hole_dx/2, sy*helmet_hole_dy/2])
                circle(d=helmet_screw_d);
        // فتحة تمرير الأسلاك
        rrect(24, 12, 3);
    }
}

module helmet_dome_cutter(t_min) {
    // قبة إهليلجية مطابقة لقياسات المسطرة (8.5 مم أمام-خلف، 11.0 مم يمين-يسار)
    translate([0, 0, -t_min - ellip_C])
        scale([ellip_A, ellip_B, ellip_C])
            sphere(r=1, $fn=96);
}

module curved_saddle_body(t_min=curved_t_min, taper_ears=true) {
    difference() {
        intersection() {
            translate([0, 0, -32])
                linear_extrude(height = 32)
                    helmet_dual_footprint_2d();
            if (taper_ears) {
                // إبقاء السطح العلوي مسطحاً للبرجين والبراغي وتقويس الأذنين لتعانق الخوذة
                union() {
                    translate([0, 0, -32]) linear_extrude(height = 32) rrect(84, 64, 5);
                    translate([0, 0, -t_min + 6.0 - ellip_C])
                        scale([ellip_A, ellip_B, ellip_C]) sphere(r=1, $fn=96);
                }
            }
        }
        helmet_dome_cutter(t_min);
    }
}

module part1_helmet_base_curved() {
    mg_cut_w = mg996_wid + tol;
    mg_cut_h = mg996_len + tol;
    z_body_c = Z_R - mg996_shaft_offset;
    union() {
        curved_saddle_body(curved_t_min, true);
        extrude_yz(p1_rear_in_x - wall, p1_rear_in_x)
        difference() {
            rbox2d(-18, -1.5, 18, 62, 4);
            translate([0, z_body_c]) square([mg_cut_w, mg_cut_h], center=true);
            for (sy=[-1, 1], sz=[-1, 1])
                translate([sy*mg996_hole_dy/2, z_body_c + sz*mg996_hole_dx/2]) circle(d=mg996_screw_d);
        }
        extrude_yz(p1_front_in_x, p1_front_in_x + wall)
        difference() {
            union() { rbox2d(-14, -1.5, 14, Z_R, 2); translate([0, Z_R]) circle(d=22); }
            translate([0, Z_R]) circle(d=pivot_bolt_d);
        }
        for (y_pos = [-13, 9])
        extrude_xz(y_pos, y_pos + 4)
            polygon([[p1_front_in_x+wall-0.5, -1.5], [p1_front_in_x+wall-0.5, 24], [p1_front_in_x+wall+10, -1.5]]);
    }
}

module part1b_curved_adapter() {
    curved_saddle_body(adapter_t_min, false);
}

module ghost_mg996r() {
    color([0.15, 0.15, 0.18, 0.65]) {
        translate([-27.5, -mg996_wid/2, -mg996_len/2 - mg996_shaft_offset]) cube([37.5, mg996_wid, mg996_len]);
        translate([0, -mg996_wid/2, -54.5/2 - mg996_shaft_offset]) cube([2.5, mg996_wid, 54.5]);
        rotate([0, 90, 0]) cylinder(d=6, h=15.5);
    }
}
module ghost_28byj48() {
    color([0.65, 0.72, 0.80, 0.75]) {
        translate([-step_shaft_offset, 0, -step_h]) cylinder(d=step_dia, h=step_h);
        translate([-step_shaft_offset, 0, -1]) cube([7, 42, 1], center=true);
        cylinder(d=5, h=10);
    }
    color([0.15, 0.45, 0.85, 0.75])
        translate([-step_shaft_offset - 12, 0, -step_h/2]) cube([10, 14.6, 17], center=true);
}
module ghost_mg90s() {
    color([0.15, 0.15, 0.2, 0.75]) {
        translate([-mg90_wid/2, 0, -mg90_len/2 - mg90_shaft_offset]) cube([mg90_wid, 22.5, mg90_len]);
        rotate([90, 0, 0]) cylinder(d=4.8, h=10.5);
    }
}

if (render_mode == "assembly") {
    color("#2E5B88") part1_helmet_base_curved();
    if (show_motors) translate([p1_rear_in_x - wall, 0, Z_R]) ghost_mg996r();

    translate([0, 0, Z_R]) rotate([preview_roll, 0, 0]) translate([0, 0, -Z_R]) {
        color("#D97224") part2_roll_u_frame();
        if (show_motors)
            translate([0, p2_pos_y_in + wall, Z_P]) rotate([90, 0, -90]) ghost_mg996r();

        translate([0, 0, Z_P]) rotate([0, preview_pitch, 0]) translate([0, 0, -Z_P]) {
            color("#2A8F55") part3_pitch_platform();
            if (show_motors) {
                translate([0, 0, z_p3_top1]) ghost_28byj48();
                color("#1E8449", 0.8) translate([18, 0, z_p3_top1 + 1.5]) cube([15.6, 20.5, 2], center=true);
            }
            rotate([0, 0, preview_yaw]) {
                color("#7B429E") part4_yaw_hub();
                if (show_motors) translate([0, 27.0, Z_TILT]) ghost_mg90s();

                translate([0, 0, Z_TILT]) rotate([0, -preview_tilt, 0]) translate([0, 0, -Z_TILT]) {
                    color("#C43A31") part5_camera_bracket();
                }
            }
        }
    }
} else if (render_mode == "part1") {
    translate([0, 0, 22]) part1_helmet_base_curved();
} else if (render_mode == "part1_flat") {
    translate([0, 0, base_thk]) part1_helmet_base();
} else if (render_mode == "part1b_adapter") {
    rotate([180, 0, 0]) part1b_curved_adapter();
} else if (render_mode == "part2") {
    translate([0, 0, -z_p2_bot0]) part2_roll_u_frame();
} else if (render_mode == "part3") {
    translate([0, 0, z_p3_top1]) rotate([180, 0, 0]) part3_pitch_platform();
} else if (render_mode == "part4") {
    translate([0, 0, 27.0]) rotate([-90, 0, 0]) part4_yaw_hub();
} else if (render_mode == "part5") {
    translate([0, 0, -(Z_TILT - 13.5)]) part5_camera_bracket();
} else if (render_mode == "print_plate") {
    translate([-60, -45, base_thk]) part1_helmet_base();
    translate([45, -45, -z_p2_bot0]) part2_roll_u_frame();
    translate([-55, 55, z_p3_top1]) rotate([180, 0, 0]) part3_pitch_platform();
    translate([25, 55, 27.0]) rotate([-90, 0, 0]) part4_yaw_hub();
    translate([80, 55, -(Z_TILT - 13.5)]) part5_camera_bracket();
}
