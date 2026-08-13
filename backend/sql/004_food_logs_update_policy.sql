-- food_logs had select/insert/delete RLS policies but no update policy, so
-- RLS silently blocked every UPDATE (0 rows affected, even for the owner) -
-- found while adding PATCH /v1/logs/{id} to support editing a logged meal's
-- quantity/meal_type/date after the fact.
create policy "owner updates own food logs"
  on food_logs for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
