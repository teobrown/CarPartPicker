-- Null out placeholder affiliate values. Every vendor was seeded with
-- affiliate_value='carbuildr' as a stand-in until real publisher codes
-- were issued. Shipping that placeholder to vendors who haven't onboarded
-- Carbuildr is noise/illegitimate attribution attempts — the /go/[id]
-- redirector gates on affiliate_param AND affiliate_value being non-null,
-- so nulling the value cleanly skips the param append.
--
-- To enable a vendor: UPDATE vendors SET affiliate_value = '<real-code>'
-- WHERE slug = '<vendor-slug>'.
UPDATE vendors SET affiliate_value = NULL WHERE affiliate_value = 'carbuildr';
