# EU-27 employment by 3-digit ISCO-08 occupation from the EU-LFS yearly microdata, and the share
# of each 3-digit occupation within its 2-digit group.
#
# Why: the exposure reweighting (compute_exposure.py, m_anchor and m_2030) uses public Eurostat
# data, which stop at 2-digit ISCO, so within each 2-digit group the US occupational mix stands in
# for the EU one. The microdata give the EU mix at 3 digits (the finest level in the SUF).
#
# Variables (EU-LFS yearly SUF, 2021+ format): COUNTRY, COEFFY (yearly weighting factor),
# ILOSTAT (1 = employed), ISCO3D (occupation in the main job, ISCO-08 3-digit, e.g. 211; armed
# forces 010-030; 999 not stated). The script looks for a few alternative names in case yours
# differ; adjust `occ_var` if needed.
#
# Usage: Rscript compute_isco3d_lfs.R   -> eulfs_employment_isco3d_2024.csv in the working directory

library(data.table)

dir  <- "G:/PUBLIC/MicroData/LFS/Microdata_2026_january/YEAR_DATA_1983_2024/Output"
file <- file.path(dir, "YearlyData_2024.csv")
eu27 <- c("AT","BE","BG","CY","CZ","DE","DK","EE","EL","ES","FI","FR","HR","HU","IE","IT",
          "LT","LU","LV","MT","NL","PL","PT","RO","SE","SI","SK")

hdr <- names(fread(file, nrows = 0))
pick <- function(cands) { v <- cands[cands %in% hdr]; if (!length(v)) stop("none of ", paste(cands, collapse = "/"), " in file"); v[1] }
occ_var <- pick(c("ISCO3D", "ISCO08_3D", "IS083D", "ISCO3"))
w_var   <- pick(c("COEFFY", "COEFF", "COEFFQ"))
st_var  <- pick(c("ILOSTAT", "WSTATOR"))
cat("using", occ_var, w_var, st_var, "\n")

d <- fread(file, select = c("COUNTRY", occ_var, w_var, st_var))
setnames(d, c("COUNTRY", occ_var, w_var, st_var), c("country", "occ", "w", "status"))
d <- d[country %in% eu27 & status == 1 & !is.na(occ) & occ > 0 & occ < 999]

# Diagnostic: countries with missing weights (they drop out of the weighted sums below)
miss <- d[, .(n = .N, weight_missing = mean(is.na(w)), weight_sum = sum(w, na.rm = TRUE)), by = country][order(-weight_missing)]
print(miss)
d <- d[!is.na(w)]
d[, occ := sprintf("%03d", as.integer(occ))]
d[, isco2d := substr(occ, 1, 2)]

# COEFFY is in thousands in the SUF (population / 1000); if your weights sum to the population
# in persons, divide by 1000 to match the Eurostat tables.
res <- d[, .(employment_ths = sum(w), n = .N), by = .(isco2d, isco3d = occ)]
res[, share_within_2d := employment_ths / sum(employment_ths), by = isco2d]
setorder(res, isco3d)
cat("EU-27 employed, total (thousand):", round(sum(res$employment_ths)), " (Eurostat lfsa_egai2d 2024: 207,173)\n")
print(res[, .(groups_2d = uniqueN(isco2d), occupations_3d = .N)])
fwrite(res, "eulfs_employment_isco3d_2024.csv")
