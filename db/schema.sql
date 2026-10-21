PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS master_product_process (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_name TEXT NOT NULL,
  process_name TEXT NOT NULL,
  product_process_name TEXT NOT NULL UNIQUE,
  product_type TEXT,
  blade_direction TEXT,
  blade_size_grade TEXT,
  crown_rotation_angle_grade TEXT,
  energy_grade TEXT,
  target_thickness_default REAL,
  is_active INTEGER NOT NULL DEFAULT 1,
  invalid_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS master_die_version (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  die_no TEXT NOT NULL,
  die_name TEXT,
  die_spec TEXT,
  die_version TEXT NOT NULL,
  die_status TEXT,
  use_count_bucket TEXT,
  total_hit_count INTEGER DEFAULT 0,
  after_repair_hit_count INTEGER DEFAULT 0,
  is_after_regrind_first_use INTEGER DEFAULT 0,
  remark TEXT,
  invalid_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(die_no, die_version)
);

CREATE TABLE IF NOT EXISTS master_die_seat (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  die_seat_no TEXT NOT NULL UNIQUE,
  theory_close_height REAL,
  seat_position_name TEXT,
  seat_x_offset REAL,
  seat_y_offset REAL,
  base_template_700 REAL,
  base_template_wear REAL DEFAULT 0,
  guide_clearance_level TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  invalid_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS master_block (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  block_no TEXT NOT NULL UNIQUE,
  block_size TEXT,
  theory_thickness REAL,
  lower_x_base REAL,
  lower_y_base REAL,
  upper_x_base REAL,
  upper_y_base REAL,
  lower_block_plate_thickness REAL,
  upper_block_plate_thickness REAL,
  block_plate_delta REAL,
  is_active INTEGER NOT NULL DEFAULT 1,
  invalid_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS master_base_plate (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plate_no TEXT NOT NULL UNIQUE,
  plate_thickness REAL NOT NULL,
  plate_remark TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  invalid_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS master_option (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category TEXT NOT NULL,
  option_value TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  remark TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(category, option_value)
);

CREATE TABLE IF NOT EXISTS master_compensation_rule (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rule_type TEXT NOT NULL,
  rule_key TEXT NOT NULL,
  x_comp REAL DEFAULT 0,
  y_comp REAL DEFAULT 0,
  template_comp REAL DEFAULT 0,
  remark TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(rule_type, rule_key)
);

CREATE TABLE IF NOT EXISTS job_install (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_no TEXT NOT NULL UNIQUE,
  job_status TEXT NOT NULL,
  job_date TEXT NOT NULL,
  shift_name TEXT NOT NULL,
  operator_name TEXT NOT NULL,
  product_process_name TEXT NOT NULL,
  die_no TEXT NOT NULL,
  die_version TEXT NOT NULL,
  die_seat_no TEXT NOT NULL,
  block_no TEXT NOT NULL,
  pass_flag INTEGER,
  remark TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_install_input (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL UNIQUE,
  base_plate_no_1 TEXT,
  base_plate_no_2 TEXT,
  base_plate_no_3 TEXT,
  base_plate_no_4 TEXT,
  base_plate_no_5 TEXT,
  die_hit_count INTEGER DEFAULT 0,
  upper_x_ref REAL NOT NULL,
  upper_y_ref REAL NOT NULL,
  lower_x_ref REAL NOT NULL,
  lower_y_ref REAL NOT NULL,
  lower_die_actual_height REAL NOT NULL,
  target_thickness REAL NOT NULL,
  upper_preheat_temp REAL,
  lower_preheat_temp REAL,
  billet_temp REAL,
  lubrication_type TEXT,
  blade_direction TEXT,
  blade_size_grade TEXT,
  crown_rotation_angle_grade TEXT,
  energy_grade TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES job_install(id)
);

CREATE TABLE IF NOT EXISTS job_calc_snapshot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL,
  calc_version TEXT NOT NULL,
  base_plate_total REAL,
  die_seat_actual_height REAL,
  die_seat_height_delta REAL,
  base_template_delta REAL,
  theory_template_thickness_base REAL,
  theory_lower_x_pad_base REAL,
  theory_lower_y_pad_base REAL,
  history_template_correction REAL,
  history_x_correction REAL,
  history_y_correction REAL,
  recommend_template_thickness REAL,
  recommend_lower_x_pad REAL,
  recommend_lower_y_pad REAL,
  similar_case_count INTEGER,
  recommend_confidence TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES job_install(id)
);

CREATE TABLE IF NOT EXISTS job_first_piece_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL,
  actual_template_thickness REAL NOT NULL,
  actual_al_block_thickness REAL,
  actual_thickness REAL,
  actual_lower_x_pad_root REAL NOT NULL,
  actual_lower_x_pad_tip REAL,
  actual_lower_y_pad REAL NOT NULL,
  measured_x_offset_root REAL NOT NULL,
  measured_x_offset_tip REAL,
  measured_y_offset REAL NOT NULL,
  first_piece_thickness_delta REAL,
  is_pass INTEGER NOT NULL,
  defect_type TEXT,
  feedback_remark TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES job_install(id)
);

CREATE TABLE IF NOT EXISTS job_sample_grade (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL UNIQUE,
  sample_grade TEXT NOT NULL,
  measure_quality_level TEXT NOT NULL,
  die_install_quality_level TEXT NOT NULL,
  block_install_quality_level TEXT NOT NULL,
  guide_clearance_level TEXT NOT NULL,
  data_completeness_level TEXT,
  grade_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES job_install(id)
);

CREATE TABLE IF NOT EXISTS job_adjustment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL,
  adjust_round INTEGER NOT NULL,
  template_delta REAL DEFAULT 0,
  x_pad_delta REAL DEFAULT 0,
  y_pad_delta REAL DEFAULT 0,
  adjust_reason TEXT,
  after_result TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES job_install(id)
);

CREATE TABLE IF NOT EXISTS job_attachment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL,
  file_type TEXT NOT NULL,
  file_path TEXT NOT NULL,
  remark TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES job_install(id)
);

CREATE TABLE IF NOT EXISTS sys_import_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  import_type TEXT NOT NULL,
  source_file TEXT NOT NULL,
  total_rows INTEGER DEFAULT 0,
  success_rows INTEGER DEFAULT 0,
  failed_rows INTEGER DEFAULT 0,
  log_text TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sys_backup_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  backup_file TEXT NOT NULL,
  backup_size INTEGER,
  remark TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_install_ppn ON job_install(product_process_name);
CREATE INDEX IF NOT EXISTS idx_job_install_die ON job_install(die_no, die_version);
CREATE INDEX IF NOT EXISTS idx_job_install_seat_block ON job_install(die_seat_no, block_no);
CREATE INDEX IF NOT EXISTS idx_feedback_job ON job_first_piece_feedback(job_id);
CREATE INDEX IF NOT EXISTS idx_grade_job ON job_sample_grade(job_id);
CREATE INDEX IF NOT EXISTS idx_calc_job_created ON job_calc_snapshot(job_id, created_at);
