# Share of job finders who switch occupation group (cognitive vs other), EU-SILC longitudinal
# files 2004-2019, one merged file per release: SILC_L_YYYY_all.csv.
#
# Input for mu_bar (Section D): the paper fits mu_bar so that the model's steady state reproduces
# the share of CPS job finders who switch group (one in seven). Before the 2021 revision SILC has
# no last-job occupation for the unemployed, so occupation is only known at interviews where the
# person is employed. Two definitions of a job finder, both pooled over countries and years:
#   (a) three interviews: employed in t-2 (occupation A), unemployed in t-1, employed in t (B);
#       two years between the occupation observations.
#   (b) calendar: employed at interviews t-1 (A) and t (B), and the monthly activity calendar of
#       wave t, which covers calendar year t-1, shows at least one month of unemployment after
#       the month of interview t-1 (any month if the interview month PB100 is missing). One year
#       between the observations, with an observed unemployment spell. The closer analogue of
#       the CPS measure, which has one month.
# Switch = A and B fall in different groups.
#
# Variables: status PL031 (2009+: 1-4 employed, 5 unemployed) or PL030 (before: 1-2 employed,
# 3 unemployed); occupation PL051 (ISCO-08, 2011+) or PL050 (ISCO-88, before), both 2-digit.
# Cognitive = major groups 1-4 plus 52 (sales), the rule of compute_share_C.py; it holds in both
# ISCO versions. A transition across 2010/2011 mixes the two versions at the group level only.
#
# Usage: Rscript compute_mu_bar_silc.R  (the folder is set in `dir` below)

library(data.table)

# SET DIR (the merged longitudinal files, one per year: SILC_L_YYYY_all.csv)
dir <- "G:/PUBLIC/MicroData/SILC/Old SILC files/Microdata_2022_January"
files <- list.files(dir, "^SILC_L_[0-9]{4}_all[.]csv$", full.names = TRUE)

# IMPORT ALL YEARS
read_one <- function(f) {
  d <- fread(f)
  setnames(d, "YEAR", "PB010")
  setnames(d, "COUNTRY", "PB020")
  setnames(d, "PERS_ID", "PB030")

  d[, release := as.integer(sub(".*SILC_L_([0-9]{4})_all.*", "\\1", f))]
  status <- if ("PL031" %in% names(d)) d$PL031 else d$PL030
  occ    <- if ("PL051" %in% names(d)) d$PL051 else d$PL050
  emp    <- if ("PL031" %in% names(d)) status %in% 1:4 else status %in% 1:2
  unemp  <- if ("PL031" %in% names(d)) status == 5 else status == 3
  cal_vars <- grep("^PL21[01][A-L]$", names(d), value = TRUE)        # PL211A-L (2009+) or PL210A-L (before)
  u_code   <- if (any(grepl("^PL211", cal_vars))) 5L else 3L
  cal      <- if (length(cal_vars)) as.matrix(d[, ..cal_vars]) else matrix(NA_integer_, nrow(d), 12)
  u_month  <- (cal == u_code)                                           # 12 columns, January to December
  u_month[is.na(u_month)] <- FALSE
  u_last   <- Reduce(pmax, lapply(1:12, function(j) ifelse(u_month[, j], j, 0L)))  # last unemployed month, 0 if none
  d[, .(release, PB010, PB020, PB030, emp, unemp, occ = suppressWarnings(as.integer(occ)),
        w = if ("RB063" %in% names(d)) RB063 else 1,
        w2 = if ("RB062" %in% names(d)) RB062 else 1,
        int_month = if ("PB100" %in% names(d)) as.integer(PB100) else NA_integer_,
        u_last = u_last)]
}
P <- rbindlist(lapply(files, read_one), fill = TRUE)

# A release holds several years of the same people; if each file holds one year, match across files.
key <- if (P[, uniqueN(PB010), by = release][, max(V1)] > 1) c("release", "PB020", "PB030") else c("PB020", "PB030")
P <- unique(P, by = c(key, "PB010"))

cognitive <- function(occ) !is.na(occ) & (occ %/% 10 %in% 1:4 | occ == 52)

e0 <- P[emp == TRUE & !is.na(occ), c(key, "PB010", "occ"), with = FALSE][, PB010 := PB010 + 2L]
u1 <- P[unemp == TRUE, c(key, "PB010"), with = FALSE][, PB010 := PB010 + 1L]
e2 <- P[emp == TRUE & !is.na(occ), c(key, "PB010", "occ", "w"), with = FALSE]
setnames(e0, "occ", "occ_before"); setnames(e2, "occ", "occ_after")
flows <- merge(merge(e0, u1, by = c(key, "PB010")), e2, by = c(key, "PB010"))

flows[, `:=`(cog_before = cognitive(occ_before), cog_after = cognitive(occ_after))]
flows[, switch := cog_before != cog_after]
flows[is.na(w), w := 0]

res <- rbind(
  flows[, .(origin = "all", n = .N, share_unw = mean(switch), share_w = weighted.mean(switch, w))],
  flows[, .(n = .N, share_unw = mean(switch), share_w = weighted.mean(switch, w)),
        by = .(origin = fifelse(cog_before, "cognitive", "other"))]
)
res[, `:=`(definition = "three interviews", years = paste(range(flows$PB010), collapse = "-"))]

# (b) calendar definition: employed at t-1 and t, unemployment months in year t-1 after interview t-1
a1 <- P[emp == TRUE & !is.na(occ), c(key, "PB010", "occ", "int_month"), with = FALSE][, PB010 := PB010 + 1L]
b1 <- P[emp == TRUE & !is.na(occ), c(key, "PB010", "occ", "w2", "u_last"), with = FALSE]
setnames(a1, "occ", "occ_before"); setnames(b1, "occ", "occ_after")
cal_flows <- merge(a1, b1, by = c(key, "PB010"))
cal_flows <- cal_flows[u_last > 0 & (is.na(int_month) | u_last > int_month)]
cal_flows[, `:=`(cog_before = cognitive(occ_before), cog_after = cognitive(occ_after))]
cal_flows[, switch := cog_before != cog_after]
cal_flows[is.na(w2), w2 := 0]
res_cal <- rbind(
  cal_flows[, .(origin = "all", n = .N, share_unw = mean(switch), share_w = weighted.mean(switch, w2))],
  cal_flows[, .(n = .N, share_unw = mean(switch), share_w = weighted.mean(switch, w2)),
            by = .(origin = fifelse(cog_before, "cognitive", "other"))]
)
res_cal[, `:=`(definition = "calendar", years = paste(range(cal_flows$PB010), collapse = "-"))]
cat("interview month PB100 available:", any(!is.na(P$int_month)), fill = TRUE)

res <- rbind(res, res_cal)
print(res)
fwrite(res, "silc_switching_shares.csv")
