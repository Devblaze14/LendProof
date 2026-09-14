-- Production Supabase databases do not run the local seed script.
-- Keep the validation engine usable after deployment by inserting the rules
-- required by loan_tape ingestion. Existing AI-generated rules are preserved.
insert into validation_rules
  (rule_key, field, rule_type, params, severity, message_template, source, active)
values
  ('required_loan_id', 'loan_id', 'required', '{}', 'critical', 'loan_id is required', 'seed', true),
  ('required_borrower_id', 'borrower_id', 'required', '{}', 'high', 'borrower_id is required', 'seed', true),
  ('valid_origination_date', 'origination_date', 'regex', '{"pattern":"^\\d{4}-\\d{2}-\\d{2}$"}', 'high', 'origination_date is not a valid ISO date', 'seed', true),
  ('maturity_after_origination', 'maturity_date', 'date_order', '{"after":"origination_date"}', 'critical', 'maturity_date must be after origination_date', 'seed', true),
  ('no_negative_principal', 'original_principal', 'range', '{"min":0}', 'critical', 'original_principal cannot be negative', 'seed', true),
  ('balance_not_exceeding_principal', 'current_balance', 'cross_field', '{"must_not_exceed":"original_principal"}', 'high', 'current_balance exceeds original_principal', 'seed', true),
  ('interest_rate_range', 'interest_rate', 'range', '{"min":0.5,"max":25.0}', 'high', 'interest_rate is outside the expected range', 'seed', true),
  ('status_dpd_consistency', 'payment_status', 'cross_field', '{"check":"status_dpd_consistency"}', 'medium', 'payment_status is inconsistent with days_past_due', 'seed', true),
  ('required_document_status', 'document_status', 'required', '{}', 'medium', 'document_status is missing', 'seed', true),
  ('stale_record', 'last_updated_at', 'staleness', '{"max_days":365}', 'low', 'record has not been updated in over a year', 'seed', true),
  ('valid_state_code', 'borrower_state', 'regex', '{"pattern":"^(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)$"}', 'medium', 'borrower_state is not a recognized US state code', 'seed', true),
  ('duplicate_loan_id', 'loan_id', 'duplicate', '{"keys":["loan_id"]}', 'critical', 'loan_id appears more than once in this batch', 'seed', true),
  ('duplicate_borrower_amount_origination', 'borrower_id', 'duplicate', '{"keys":["borrower_id","original_principal","origination_date"]}', 'high', 'borrower_id + original_principal + origination_date combination repeats', 'seed', true),
  ('closed_positive_balance', 'payment_status', 'cross_field', '{"check":"closed_zero_balance"}', 'high', 'loan is marked closed but still shows a positive balance', 'seed', true),
  ('cross_file_conflict', null, 'cross_file', '{"source":"servicer_update"}', 'medium', 'value conflicts with servicer_update.csv', 'seed', true)
on conflict (rule_key) do nothing;
