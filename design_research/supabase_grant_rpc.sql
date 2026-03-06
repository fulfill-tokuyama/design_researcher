-- Fix 404 NOT_FOUND on match_designs RPC
-- Run this in Supabase Dashboard > SQL Editor if --search returns 404

-- Grant RPC execute permission to anon (Publishable Key)
GRANT EXECUTE ON FUNCTION public.match_designs(vector, double precision, integer, text, double precision) TO anon;
GRANT EXECUTE ON FUNCTION public.match_designs(vector, double precision, integer, text, double precision) TO authenticated;

-- If above fails, try granting all functions in public schema:
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon;
