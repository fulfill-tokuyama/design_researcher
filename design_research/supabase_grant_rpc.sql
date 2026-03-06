-- Fix 404 NOT_FOUND on match_designs RPC
-- Run this in Supabase Dashboard > SQL Editor if --search returns 404

-- Step 1: Reload PostgREST schema cache (required after creating new functions)
NOTIFY pgrst, 'reload schema';

-- Step 2: Grant RPC execute permission to anon (Publishable Key)
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;

-- Step 3: Wait a few seconds, then retry: python supabase_store.py --search "query"
